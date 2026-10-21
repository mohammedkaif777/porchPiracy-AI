"""Event classification: tracks in, meaningful events out.

The geometry helpers at the top of this module are **pure functions** and carry
the unit tests (``tests/unit/test_event_classifier.py``). The classifier itself
keeps a :class:`SceneState` describing what has been seen so far and emits an
event only on a state change or after a cooldown, never once per frame.

The module never touches the database or the network: it returns
``EventCreate`` objects that the caller forwards through a callback.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.core.logging_config import get_logger
from backend.schemas.enums import EventType
from backend.schemas.event_schema import EventCreate, Track

logger = get_logger(__name__)

BBox = Sequence[float]
Zone = Sequence[Sequence[float]]


# --------------------------------------------------------------------- geometry


def bbox_center(bbox: BBox) -> tuple[float, float]:
    """Return the centre point ``(cx, cy)`` of a bounding box."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def bbox_width(bbox: BBox) -> float:
    """Return the width of a bounding box."""
    return float(bbox[2] - bbox[0])


def bbox_height(bbox: BBox) -> float:
    """Return the height of a bounding box."""
    return float(bbox[3] - bbox[1])


def bbox_iou(box_a: BBox, box_b: BBox) -> float:
    """Return the intersection over union of two bounding boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return float(intersection / union)


def bbox_distance(box_a: BBox, box_b: BBox) -> float:
    """Return the shortest distance between two boxes. Zero when they overlap."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    dx = max(bx1 - ax2, ax1 - bx2, 0.0)
    dy = max(by1 - ay2, ay1 - by2, 0.0)
    return float((dx * dx + dy * dy) ** 0.5)


def centroid_displacement(current: BBox | tuple[float, float], baseline: BBox | tuple[float, float]) -> float:
    """Return the distance between the centres of two boxes or two points."""
    current_point = current if len(current) == 2 else bbox_center(current)  # type: ignore[arg-type]
    baseline_point = baseline if len(baseline) == 2 else bbox_center(baseline)  # type: ignore[arg-type]
    dx = float(current_point[0]) - float(baseline_point[0])  # type: ignore[index]
    dy = float(current_point[1]) - float(baseline_point[1])  # type: ignore[index]
    return float((dx * dx + dy * dy) ** 0.5)


def point_in_polygon(point: tuple[float, float], polygon: Zone) -> bool:
    """Return whether a point lies inside a polygon (ray casting).

    An empty or degenerate polygon returns ``False``.
    """
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    count = len(polygon)
    previous_x, previous_y = polygon[count - 1]
    for index in range(count):
        current_x, current_y = polygon[index]
        if (current_y > y) != (previous_y > y):
            denominator = current_y - previous_y
            if denominator != 0:
                crossing_x = current_x + (y - current_y) * (previous_x - current_x) / denominator
                if x < crossing_x:
                    inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def is_near(
    person_bbox: BBox,
    package_bbox: BBox,
    distance_px: float = 150.0,
    threshold: float | None = None,
) -> bool:
    """Return whether a person is close enough to the package to be "near" it."""
    limit = threshold if threshold is not None else distance_px
    return bbox_distance(person_bbox, package_bbox) <= limit


def is_interaction(person_bbox: BBox, package_bbox: BBox, iou_threshold: float) -> bool:
    """Return whether a person overlaps the package (contact)."""
    return bbox_iou(person_bbox, package_bbox) >= iou_threshold


# ------------------------------------------------------------------- classifier


@dataclass
class EventClassifierConfig:
    """Geometry thresholds used by the classifier. Passed in, never read globally."""

    near_distance_px: float = 150.0
    interaction_iou_threshold: float = 0.1
    interaction_frames_required: int = 3
    package_movement_px: float = 60.0
    package_removed_seconds: float = 3.0
    loiter_threshold_seconds: float = 8.0
    event_cooldown_seconds: float = 2.0
    protection_zone: Zone | None = None

    @classmethod
    def from_settings(cls, settings) -> EventClassifierConfig:  # noqa: ANN001 - avoids an import cycle
        """Build the configuration from the application settings."""
        return cls(
            near_distance_px=settings.near_package_distance_px,
            interaction_iou_threshold=settings.interaction_iou_threshold,
            interaction_frames_required=settings.interaction_frames_required,
            package_movement_px=settings.package_movement_px,
            package_removed_seconds=settings.package_removed_seconds,
            loiter_threshold_seconds=settings.loiter_threshold_seconds,
            event_cooldown_seconds=settings.event_cooldown_seconds,
        )


@dataclass
class SceneState:
    """What the classifier has seen so far in the current video."""

    package_track_id: int | None = None
    package_baseline_center: tuple[float, float] | None = None
    package_center: tuple[float, float] | None = None
    package_last_seen_s: float | None = None
    package_last_bbox: list[float] = field(default_factory=list)
    near_since: dict[int, float] = field(default_factory=dict)
    last_near_at: dict[int, float] = field(default_factory=dict)
    interaction_frames: dict[int, int] = field(default_factory=dict)
    last_emitted: dict[tuple[str, int], float] = field(default_factory=dict)
    authorized_retrieval: bool = False
    removal_reported: bool = False


class EventClassifier:
    """Turns per-frame tracks into events using the geometry rules."""

    def __init__(self, config: EventClassifierConfig | None = None) -> None:
        self._config = config or EventClassifierConfig()

    @property
    def config(self) -> EventClassifierConfig:
        """Return the active configuration."""
        return self._config

    def classify_events(
        self,
        tracks: Sequence[Track],
        t: float,
        state: SceneState,
    ) -> list[EventCreate]:
        """Classify one frame of tracks into events.

        Args:
            tracks: Tracks of the current frame.
            t: Timestamp of the frame in seconds.
            state: Scene state, updated in place.

        Returns:
            The events emitted for this frame. Usually empty.
        """
        events: list[EventCreate] = []
        people = [track for track in tracks if track.cls == "person"]
        packages = [track for track in tracks if track.cls == "package"]

        package = packages[0] if packages else None
        self._update_package(package, t, state, events)

        for person in people:
            self._update_person(person, package, t, state, events)

        self._check_removal(t, state, events)
        return events

    # ------------------------------------------------------------------ pieces

    def _update_package(
        self,
        package: Track | None,
        t: float,
        state: SceneState,
        events: list[EventCreate],
    ) -> None:
        """Track the package and emit detection and movement events."""
        if package is None:
            return

        center = bbox_center(package.bbox)
        if state.package_track_id is None:
            state.package_track_id = package.track_id
            state.package_baseline_center = center
            event = self._build_event(
                EventType.PACKAGE_DETECTED,
                t,
                state,
                track_ids={"package": package.track_id},
                bbox={"package": list(package.bbox)},
                confidence=package.confidence,
                metadata={"center": list(center)},
            )
            if event is not None:
                events.append(event)
        state.package_center = center
        state.package_last_seen_s = t
        state.package_last_bbox = list(package.bbox)

        if state.package_baseline_center is not None:
            displacement = centroid_displacement(center, state.package_baseline_center)
            if displacement >= self._config.package_movement_px:
                event = self._build_event(
                    EventType.PACKAGE_MOVEMENT_DETECTED,
                    t,
                    track_ids={"package": package.track_id},
                    bbox={"package": list(package.bbox)},
                    confidence=package.confidence,
                    metadata={
                        "displacement_px": round(displacement, 2),
                        "baseline_center": list(state.package_baseline_center),
                    },
                    cooldown_key=("package_movement", package.track_id),
                )
                if event is not None:
                    events.append(event)

    def _update_person(
        self,
        person: Track,
        package: Track | None,
        t: float,
        state: SceneState,
        events: list[EventCreate],
    ) -> None:
        """Emit approaching, near, loitering and interaction events for a person."""
        if package is None:
            return

        person_center = bbox_center(person.bbox)
        inside_zone = bool(
            self._config.protection_zone
            and point_in_polygon(person_center, self._config.protection_zone)
        )
        distance = bbox_distance(person.bbox, package.bbox)
        near = inside_zone or distance <= self._config.near_distance_px

        if not near:
            state.near_since.pop(person.track_id, None)
            state.interaction_frames[person.track_id] = 0
            return

        state.last_near_at[person.track_id] = t
        if person.track_id not in state.near_since:
            state.near_since[person.track_id] = t
            event = self._build_event(
                EventType.PERSON_NEAR_PACKAGE,
                t,
                state,
                track_ids={"person": person.track_id, "package": package.track_id},
                bbox={"person": list(person.bbox), "package": list(package.bbox)},
                confidence=person.confidence,
                metadata={
                    "distance_px": round(distance, 2),
                    "inside_zone": inside_zone,
                },
                cooldown_key=("person_near", person.track_id),
            )
            if event is not None:
                events.append(event)

        near_since = state.near_since.get(person.track_id, t)
        stay = t - near_since
        if stay >= self._config.loiter_threshold_seconds:
            event = self._build_event(
                EventType.LOITERING_DETECTED,
                t,
                state,
                track_ids={"person": person.track_id, "package": package.track_id},
                bbox={"person": list(person.bbox), "package": list(package.bbox)},
                confidence=person.confidence,
                metadata={"duration_s": round(stay, 2)},
                cooldown_key=("loitering", person.track_id),
            )
            if event is not None:
                events.append(event)

        if is_interaction(person.bbox, package.bbox, self._config.interaction_iou_threshold):
            state.interaction_frames[person.track_id] = state.interaction_frames.get(person.track_id, 0) + 1
            if state.interaction_frames[person.track_id] >= self._config.interaction_frames_required:
                event = self._build_event(
                    EventType.PACKAGE_INTERACTION,
                    t,
                    state,
                    track_ids={"person": person.track_id, "package": package.track_id},
                    bbox={"person": list(person.bbox), "package": list(package.bbox)},
                    confidence=person.confidence,
                    metadata={
                        "frames": state.interaction_frames[person.track_id],
                        "iou": round(bbox_iou(person.bbox, package.bbox), 3),
                    },
                    cooldown_key=("interaction", person.track_id),
                )
                if event is not None:
                    events.append(event)
        else:
            state.interaction_frames[person.track_id] = 0

    def _check_removal(self, t: float, state: SceneState, events: list[EventCreate]) -> None:
        """Emit a removal event when the package vanished next to a person."""
        if state.package_last_seen_s is None or state.removal_reported:
            return
        if t - state.package_last_seen_s < self._config.package_removed_seconds:
            return

        associated = [
            track_id
            for track_id, last_seen in state.last_near_at.items()
            if state.package_last_seen_s - last_seen <= self._config.package_removed_seconds
        ]
        if not associated:
            return

        state.removal_reported = True
        event = self._build_event(
            EventType.PACKAGE_REMOVED,
            t,
            state,
            track_ids={"package": state.package_track_id} if state.package_track_id else {},
            bbox={"package": state.package_last_bbox} if state.package_last_bbox else {},
            confidence=1.0,
            metadata={
                "last_seen_s": round(state.package_last_seen_s, 2),
                "associated_person_track_ids": associated,
            },
        )
        if event is not None:
            events.append(event)

    # ----------------------------------------------------------------- helpers

    def _build_event(
        self,
        event_type: EventType,
        t: float,
        state: SceneState,
        track_ids: dict[str, int] | None = None,
        bbox: dict[str, list[float]] | None = None,
        confidence: float = 1.0,
        metadata: dict | None = None,
        cooldown_key: tuple[str, int] | None = None,
    ) -> EventCreate | None:
        """Build an event, honouring the emission cooldown.

        Events without a cooldown key are always emitted; they mark a state
        change and cannot repeat. Returns ``None`` when the cooldown suppressed
        the event.
        """
        if cooldown_key is not None:
            last = state.last_emitted.get(cooldown_key)
            if last is not None and t - last < self._config.event_cooldown_seconds:
                return None
            state.last_emitted[cooldown_key] = t
        return EventCreate(
            event_id=str(uuid.uuid4()),
            type=event_type,
            timestamp_s=round(float(t), 3),
            frame_index=int(round(t * 30)),
            track_ids=track_ids or {},
            confidence=round(float(confidence), 4),
            bbox=bbox or {},
            metadata=metadata or {},
        )


def classify_events(
    tracks: Sequence[Track],
    t: float,
    state: SceneState,
    config: EventClassifierConfig | None = None,
) -> list[EventCreate]:
    """Classify a frame of tracks into events (functional wrapper).

    Args:
        tracks: Tracks of the current frame.
        t: Timestamp of the frame in seconds.
        state: Scene state, updated in place.
        config: Geometry thresholds.

    Returns:
        The events emitted for this frame.
    """
    classifier = EventClassifier(config)
    return classifier.classify_events(tracks, t, state)


def build_event_classifier(settings=None) -> EventClassifier:  # noqa: ANN001 - avoids an import cycle
    """Build a classifier from the application settings."""
    if settings is None:
        from backend.core.config import get_settings  # noqa: PLC0415 - lazy on purpose

        settings = get_settings()
    return EventClassifier(EventClassifierConfig.from_settings(settings))
