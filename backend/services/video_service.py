"""Video pipeline: frames in, annotated video and events out.

``analyze_video`` is the orchestrator of the vision layer. It never touches the
database or the network: events are handed to an ``on_event`` callback, which
the API wires to the event ingestion endpoint.

Run it standalone to test the pipeline without the API::

    python -m backend.services.video_service samples/videos/porch.mp4
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import Settings, get_settings
from backend.core.exceptions import VisionDependencyError
from backend.core.logging_config import get_logger
from backend.schemas.event_schema import EventCreate
from backend.services.detection_service import DetectionService
from backend.services.event_service import EventClassifier, EventClassifierConfig, SceneState
from backend.services.tracking_service import TrackingService

logger = get_logger(__name__)

EventCallback = Callable[[EventCreate], None]
ProgressCallback = Callable[[float, float, int], None]


@dataclass
class AnalysisResult:
    """Outcome of a video analysis run."""

    video_path: str
    annotated_path: str | None = None
    events: list[EventCreate] = field(default_factory=list)
    frames_processed: int = 0
    total_frames: int = 0
    duration_s: float = 0.0
    elapsed_s: float = 0.0
    error: str | None = None

    @property
    def effective_fps(self) -> float:
        """Return the processing speed in frames per second."""
        if self.elapsed_s <= 0:
            return 0.0
        return self.frames_processed / self.elapsed_s


def _import_cv2() -> Any:
    """Import OpenCV lazily and raise a friendly error when it is missing."""
    try:
        import cv2  # noqa: PLC0415 - lazy on purpose
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise VisionDependencyError("opencv-python is not installed") from exc
    return cv2


def analyze_video(
    path: str | Path,
    session_id: str | None = None,
    on_event: EventCallback | None = None,
    settings: Settings | None = None,
    progress_callback: ProgressCallback | None = None,
    protection_zone: list[list[float]] | None = None,
    write_annotated: bool = True,
) -> AnalysisResult:
    """Run the full vision pipeline over a video file.

    Args:
        path: Path of the video to analyse.
        session_id: Session the events belong to.
        on_event: Callback invoked for every event, in chronological order.
        settings: Application settings.
        progress_callback: Called with ``(progress, current_time_s, frame_index)``.
        protection_zone: Polygon drawn on the annotated video.
        write_annotated: Whether to write the annotated copy.

    Returns:
        An :class:`AnalysisResult` with the events and the output paths.
    """
    config = settings or get_settings()
    cv2 = _import_cv2()

    video_path = Path(path)
    if not video_path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")

    config.ensure_directories()

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise VisionDependencyError(f"could not open the video file {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS) or config.annotated_fps_fallback
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    detector = DetectionService(settings=config)
    tracker = TrackingService()
    classifier_config = EventClassifierConfig.from_settings(config)
    if protection_zone:
        classifier_config.protection_zone = protection_zone
    classifier = EventClassifier(classifier_config)
    scene_state = SceneState()

    annotated_path: Path | None = None
    writer = None
    if write_annotated:
        annotated_path = config.annotated_dir / f"{video_path.stem}_annotated.mp4"
        writer = cv2.VideoWriter(
            str(annotated_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )

    result = AnalysisResult(
        video_path=str(video_path),
        annotated_path=str(annotated_path) if annotated_path else None,
        total_frames=total_frames,
    )

    started = time.perf_counter()
    frame_index = 0
    stride = max(1, config.frame_stride)
    tracks: list[Any] = []

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            timestamp = frame_index / fps if fps else 0.0
            if frame_index % stride == 0:
                try:
                    detections = detector.detect(frame)
                    tracks = tracker.update_tracks(detections)
                    events = classifier.classify_events(tracks, timestamp, scene_state)
                    for event in events:
                        if session_id:
                            event.session_id = session_id
                        result.events.append(event)
                        if on_event is not None:
                            on_event(event)
                except VisionDependencyError:
                    raise
                except Exception:  # pragma: no cover - defensive, a frame must not kill the run
                    logger.exception("Frame %s could not be processed", frame_index)

            if writer is not None:
                annotated = draw_annotations(frame, tracks, protection_zone)
                writer.write(annotated)

            frame_index += 1
            if progress_callback is not None:
                progress = (frame_index / total_frames) if total_frames else 0.0
                progress_callback(min(progress, 1.0), timestamp, frame_index)
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    result.frames_processed = frame_index
    result.duration_s = (frame_index / fps) if fps else 0.0
    result.elapsed_s = time.perf_counter() - started
    logger.info(
        "Analysis finished: %s frames=%s events=%s fps=%.1f",
        video_path.name,
        result.frames_processed,
        len(result.events),
        result.effective_fps,
    )
    return result


def draw_annotations(
    frame: Any,
    tracks: list[Any],
    protection_zone: list[list[float]] | None = None,
) -> Any:
    """Draw boxes, track ids and the protection zone onto a frame."""
    cv2 = _import_cv2()

    output = frame.copy()
    if protection_zone and len(protection_zone) >= 3:
        points = np_points(protection_zone)
        cv2.polylines(output, [points], isClosed=True, color=(0, 255, 255), thickness=2)

    for track in tracks:
        x1, y1, x2, y2 = (int(value) for value in track.bbox)
        colour = (0, 220, 0) if track.cls == "person" else (255, 160, 0)
        cv2.rectangle(output, (x1, y1), (x2, y2), colour, 2)
        label = f"{track.cls} #{track.track_id}"
        cv2.putText(
            output,
            label,
            (x1, max(15, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            colour,
            2,
        )
    return output


def np_points(points: list[list[float]]) -> Any:
    """Convert a list of 2D points into a numpy array of int32."""
    import numpy as np  # noqa: PLC0415 - lazy on purpose

    return np.array(points, dtype="int32").reshape(-1, 1, 2)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: analyse a video and print the events as JSON."""
    parser = argparse.ArgumentParser(description="Run the porchPiracyAI vision pipeline on a video.")
    parser.add_argument("video", help="Path of the video file")
    parser.add_argument("--session-id", default=None, help="Session id attached to the events")
    parser.add_argument("--stride", type=int, default=None, help="Process every Nth frame")
    parser.add_argument("--no-annotated", action="store_true", help="Do not write the annotated video")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.stride:
        settings.frame_stride = args.stride

    try:
        result = analyze_video(
            args.video,
            session_id=args.session_id,
            settings=settings,
            write_annotated=not args.no_annotated,
        )
    except (VisionDependencyError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1

    print(json.dumps([event.model_dump(mode="json") for event in result.events], indent=2))
    print(
        f"\n{result.frames_processed} frames, {len(result.events)} events, "
        f"{result.effective_fps:.1f} effective FPS, annotated: {result.annotated_path}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
