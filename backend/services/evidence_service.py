"""Evidence capture: clip, key frames, face blur and metadata.

Everything stays on the local disk. Faces are blurred before a clip is written
so an exported report never carries an identifiable face.

The module degrades gracefully: without OpenCV it returns an empty bundle and
reports why, instead of failing the incident pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import Settings, get_settings
from backend.core.logging_config import get_logger
from backend.models.incident import Incident

logger = get_logger(__name__)

CLIP_PADDING_SECONDS = 5.0
KEY_FRAME_COUNT = 3


@dataclass
class EvidenceResult:
    """The evidence bundle produced for an incident."""

    incident_id: str
    clip_path: str | None = None
    clip_start_s: float | None = None
    clip_end_s: float | None = None
    key_frames: list[dict] = field(default_factory=list)
    faces_blurred: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a JSON friendly representation."""
        return {
            "incident_id": self.incident_id,
            "clip_path": self.clip_path,
            "clip_start_s": self.clip_start_s,
            "clip_end_s": self.clip_end_s,
            "key_frames": self.key_frames,
            "faces_blurred": self.faces_blurred,
            "metadata": self.metadata,
        }


def _import_cv2() -> Any:
    """Import OpenCV lazily and return ``None`` when it is unavailable."""
    try:
        import cv2  # noqa: PLC0415 - lazy on purpose
    except ImportError:  # pragma: no cover - depends on the environment
        logger.warning("opencv-python is not installed, evidence capture is disabled")
        return None
    return cv2


def _face_cascade(cv2: Any) -> Any:
    """Return the Haar cascade used for face detection, or ``None``."""
    try:
        path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        if not path.is_file():
            return None
        cascade = cv2.CascadeClassifier(str(path))
        if cascade.empty():
            return None
        return cascade
    except Exception:  # pragma: no cover - defensive
        return None


def blur_faces(frame: Any, cv2: Any) -> tuple[Any, int]:
    """Blur every detected face in a frame.

    Returns:
        The processed frame and the number of blurred faces.
    """
    cascade = _face_cascade(cv2)
    if cascade is None:
        return frame, 0

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    blurred = frame.copy()
    for x, y, w, h in faces:
        region = blurred[y : y + h, x : x + w]
        blurred[y : y + h, x : x + w] = cv2.GaussianBlur(region, (21, 21), 0)
    return blurred, len(faces)


def create_evidence(
    video_path: str | Path,
    incident: Incident,
    settings: Settings | None = None,
    padding_seconds: float = CLIP_PADDING_SECONDS,
) -> EvidenceResult:
    """Cut an evidence clip and save key frames for an incident.

    Args:
        video_path: Path of the original video.
        incident: The incident the evidence belongs to.
        settings: Application settings.
        padding_seconds: Extra seconds kept before and after the incident.

    Returns:
        The evidence bundle. ``clip_path`` is ``None`` when the clip could not
        be produced (missing OpenCV or missing video).
    """
    config = settings or get_settings()
    config.ensure_directories()

    result = EvidenceResult(
        incident_id=incident.incident_id,
        clip_start_s=max(0.0, incident.start_s - padding_seconds),
        clip_end_s=incident.end_s + padding_seconds,
        metadata={
            "reason_codes": list(incident.reason_codes),
            "severity": incident.severity,
            "event_ids": list(incident.event_ids),
            "start_s": incident.start_s,
            "end_s": incident.end_s,
        },
    )

    source = Path(video_path)
    if not source.is_file():
        result.metadata["error"] = f"Source video not found: {source}"
        return result

    cv2 = _import_cv2()
    if cv2 is None:
        result.metadata["error"] = "opencv-python is not installed"
        return result

    output_dir = config.evidence_dir / f"inc_{incident.incident_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    clip_path = output_dir / "clip.mp4"

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        result.metadata["error"] = f"Could not open the video {source}"
        return result

    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    writer = cv2.VideoWriter(
        str(clip_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )

    key_frame_targets = _key_frame_timestamps(result.clip_start_s, result.clip_end_s)
    saved_frames: list[dict] = []
    blurred_count = 0
    frame_index = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_index / fps if fps else 0.0
            if result.clip_start_s is not None and result.clip_end_s is not None:
                if result.clip_start_s <= timestamp <= result.clip_end_s:
                    processed, blurred = blur_faces(frame, cv2)
                    blurred_count += blurred
                    writer.write(processed)
                    for target in list(key_frame_targets):
                        if abs(timestamp - target["timestamp_s"]) <= 0.5:
                            path = output_dir / f"frame_{int(target['timestamp_s'])}.jpg"
                            cv2.imwrite(str(path), processed)
                            saved_frames.append(
                                {"path": str(path), "timestamp_s": round(timestamp, 2), "label": target["label"]}
                            )
                            key_frame_targets.remove(target)
            frame_index += 1
    finally:
        capture.release()
        writer.release()

    if not clip_path.is_file() or clip_path.stat().st_size == 0:
        result.metadata["error"] = "The evidence clip could not be written"
        return result

    result.clip_path = str(clip_path)
    result.key_frames = saved_frames
    result.faces_blurred = True
    result.metadata["frames_written"] = frame_index
    result.metadata["blurred_faces"] = blurred_count
    logger.info(
        "Evidence created incident_id=%s clip=%s key_frames=%s",
        incident.incident_id,
        result.clip_path,
        len(saved_frames),
    )
    return result


def _key_frame_timestamps(start_s: float | None, end_s: float | None) -> list[dict]:
    """Return the timestamps of the key frames to extract."""
    if start_s is None or end_s is None:
        return []
    span = max(0.0, end_s - start_s)
    offsets = [0.0, span / 2, span]
    labels = ["start", "middle", "end"]
    return [
        {"timestamp_s": start_s + offset, "label": label}
        for offset, label in zip(offsets, labels)
    ]


def write_metadata(result: EvidenceResult, output_dir: Path) -> Path:
    """Write the evidence metadata next to the clip as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "metadata.json"
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path
