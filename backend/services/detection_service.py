"""Detection service: frames in, :class:`Detection` objects out.

The heavy dependencies (``ultralytics``) are imported lazily so the API, the
dashboard and the test suite run on a machine without the ML stack. The models
are loaded once and cached for the lifetime of the service.

Person detection uses a COCO YOLO model (class ``person``). There is no
``package`` class in COCO, so package detection uses, in order of preference:

1. a dedicated package model at ``PACKAGE_MODEL_PATH``;
2. COCO proxy classes (``suitcase``, ``handbag``, ``backpack``) from the person
   model, used as a fallback so the pipeline runs end to end on day one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.config import Settings, get_settings
from backend.core.exceptions import VisionDependencyError
from backend.core.logging_config import get_logger
from backend.schemas.event_schema import Detection

logger = get_logger(__name__)

PERSON_CLASS = "person"
PACKAGE_CLASS = "package"


class DetectionService:
    """Runs the detectors over frames and returns normalised detections."""

    def __init__(
        self,
        settings: Settings | None = None,
        person_model_path: Path | str | None = None,
        package_model_path: Path | str | None = None,
        conf_threshold: float | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._person_model_path = Path(
            person_model_path or self._settings.person_model_path
        )
        self._package_model_path = Path(
            package_model_path or self._settings.package_model_path
        )
        self._conf_threshold = (
            self._settings.detection_conf_threshold if conf_threshold is None else conf_threshold
        )
        self._proxy_classes = set(self._settings.coco_package_proxy_classes)
        self._person_model: Any = None
        self._package_model: Any = None
        self._package_model_available = self._package_model_path.is_file()

    # ------------------------------------------------------------------ models

    def _load_yolo(self, path: Path) -> Any:
        """Load a YOLO model, raising a friendly error when unavailable."""
        try:
            from ultralytics import YOLO  # noqa: PLC0415 - lazy on purpose
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise VisionDependencyError(
                "ultralytics is not installed (needed for 'ultralytics')"
            ) from exc

        try:
            logger.info("Loading detection model from %s", path)
            return YOLO(str(path))
        except Exception as exc:  # pragma: no cover - depends on the environment
            raise VisionDependencyError(f"could not load the model at {path}: {exc}") from exc

    @property
    def person_model(self) -> Any:
        """Return the cached person model, loading it on first use."""
        if self._person_model is None:
            self._person_model = self._load_yolo(self._person_model_path)
        return self._person_model

    @property
    def package_model(self) -> Any:
        """Return the cached package model, or ``None`` when it is not available."""
        if not self._package_model_available:
            return None
        if self._package_model is None:
            self._package_model = self._load_yolo(self._package_model_path)
        return self._package_model

    @property
    def uses_proxy_package_classes(self) -> bool:
        """True when packages are detected through the COCO proxy classes."""
        return not self._package_model_available

    # --------------------------------------------------------------- inference

    def detect(self, frame: Any) -> list[Detection]:
        """Detect people and packages in one frame.

        Args:
            frame: A BGR image as a numpy array.

        Returns:
            The detections above the confidence threshold.

        Raises:
            VisionDependencyError: If the vision stack is not installed.
        """
        detections: list[Detection] = []
        detections.extend(self._detect_persons(frame))

        package_model = self.package_model
        if package_model is not None:
            detections.extend(self._detect_packages(frame, package_model, proxy=False))
        else:
            detections.extend(self._detect_packages(frame, self.person_model, proxy=True))
        return detections

    def _detect_persons(self, frame: Any) -> list[Detection]:
        """Detect people using the person model."""
        results = self.person_model.predict(frame, conf=self._conf_threshold, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = getattr(result, "names", {}) or {}
            boxes = result.boxes
            for class_index, box, confidence in zip(
                boxes.cls.tolist(), boxes.xyxy.tolist(), boxes.conf.tolist()
            ):
                class_name = str(names.get(int(class_index), class_index))
                if class_name != PERSON_CLASS:
                    continue
                detections.append(
                    Detection(cls=PERSON_CLASS, bbox=box, confidence=float(confidence))
                )
        return detections

    def _detect_packages(self, frame: Any, model: Any, proxy: bool) -> list[Detection]:
        """Detect packages, either with a dedicated model or the COCO proxies."""
        results = model.predict(frame, conf=self._conf_threshold, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = getattr(result, "names", {}) or {}
            for class_index, box, confidence in zip(
                result.boxes.cls.tolist(),
                result.boxes.xyxy.tolist(),
                result.boxes.conf.tolist(),
            ):
                class_name = str(names.get(int(class_index), class_index))
                if proxy and class_name not in self._proxy_classes:
                    continue
                detections.append(
                    Detection(cls=PACKAGE_CLASS, bbox=box, confidence=float(confidence))
                )
        return detections


def build_detection_service(settings: Settings | None = None) -> DetectionService:
    """Factory used by the API and the video pipeline."""
    return DetectionService(settings=settings)
