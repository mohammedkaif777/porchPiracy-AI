"""Tracking service: detections in, tracked objects with stable ids out.

ByteTrack (``supervision``, MIT licensed) is used when it is installed. When it
is not, a small IoU-based tracker keeps the pipeline working, so the API and the
demo never depend on an optional package.

Track ids are only unique inside a single video. They are never used to identify
a person across videos.
"""

from __future__ import annotations

from typing import Any

from backend.core.logging_config import get_logger
from backend.schemas.event_schema import Detection, Track

logger = get_logger(__name__)

#: Numeric class ids used by the tracker: 0 = person, 1 = package.
CLASS_IDS: dict[str, int] = {"person": 0, "package": 1}
CLASS_NAMES: dict[int, str] = {value: key for key, value in CLASS_IDS.items()}


class TrackingService:
    """Turns per-frame detections into tracked objects with stable ids."""

    def __init__(self) -> None:
        self._tracker: Any = None
        self._use_supervision = True
        self._next_id = 1
        self._fallback_tracks: list[Track] = []

    # ---------------------------------------------------------------- helpers

    def _get_tracker(self) -> Any:
        """Return the ByteTrack tracker, or ``None`` when supervision is missing."""
        if self._tracker is None and self._use_supervision:
            try:
                from supervision import ByteTrack  # noqa: PLC0415 - lazy on purpose

                self._tracker = ByteTrack()
                logger.info("Tracking with supervision ByteTrack")
            except ImportError:
                self._use_supervision = False
                logger.warning(
                    "supervision is not installed, falling back to the built-in IoU tracker"
                )
        return self._tracker

    # ------------------------------------------------------------------ public

    def update_tracks(self, detections: list[Detection]) -> list[Track]:
        """Update the tracker with a frame of detections.

        Args:
            detections: Detections of the current frame.

        Returns:
            The tracks currently alive, with their stable ids.
        """
        tracker = self._get_tracker()
        if tracker is not None:
            return self._update_with_byte_track(tracker, detections)
        return self._update_with_fallback(detections)

    def reset(self) -> None:
        """Forget every track. Called when a new video starts."""
        self._next_id = 1
        self._fallback_tracks = []
        tracker = self._get_tracker()
        if tracker is not None and hasattr(tracker, "reset"):
            tracker.reset()

    # -------------------------------------------------------------- supervision

    def _update_with_byte_track(self, tracker: Any, detections: list[Detection]) -> list[Track]:
        """Update using supervision ByteTrack."""
        import numpy as np  # noqa: PLC0415 - lazy on purpose
        from supervision import Detections  # noqa: PLC0415 - lazy on purpose

        if not detections:
            return []

        xyxy = np.array([detection.bbox for detection in detections], dtype=float)
        class_id = np.array([CLASS_IDS.get(detection.cls, 0) for detection in detections], dtype=int)
        confidence = np.array([detection.confidence for detection in detections], dtype=float)

        sv_detections = Detections(xyxy=xyxy, class_id=class_id, confidence=confidence)
        tracked = tracker.update_with_detections(sv_detections)

        tracks: list[Track] = []
        for index in range(len(tracked)):
            tracker_id = tracked.tracker_id[index]
            if tracker_id is None:
                continue
            class_index = int(tracked.class_id[index])
            score = float(tracked.confidence[index]) if tracked.confidence is not None else 1.0
            tracks.append(
                Track(
                    track_id=int(tracker_id),
                    cls=CLASS_NAMES.get(class_index, "person"),
                    bbox=[float(value) for value in tracked.xyxy[index].tolist()],
                    confidence=score,
                )
            )
        return tracks

    # ---------------------------------------------------------------- fallback

    def _update_with_fallback(self, detections: list[Detection]) -> list[Track]:
        """Update using the built-in IoU tracker."""
        from backend.services.event_service import bbox_iou  # noqa: PLC0415 - avoids a cycle

        unmatched = list(self._fallback_tracks)
        tracks: list[Track] = []

        for detection in detections:
            best_index = -1
            best_iou = 0.0
            for index, candidate in enumerate(unmatched):
                iou = bbox_iou(candidate.bbox, detection.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_index = index

            if best_index >= 0 and best_iou >= 0.2:
                previous = unmatched.pop(best_index)
                tracks.append(
                    Track(
                        track_id=previous.track_id,
                        cls=detection.cls,
                        bbox=list(detection.bbox),
                        confidence=detection.confidence,
                    )
                )
            else:
                tracks.append(
                    Track(
                        track_id=self._next_id,
                        cls=detection.cls,
                        bbox=list(detection.bbox),
                        confidence=detection.confidence,
                    )
                )
                self._next_id += 1

        self._fallback_tracks = tracks
        return tracks
