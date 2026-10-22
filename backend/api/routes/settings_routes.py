"""Settings read and update endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import app_settings
from backend.core.config import Settings, reload_settings
from backend.core.logging_config import get_logger
from backend.schemas.system_schema import SettingsRead, SettingsUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
def read_settings(settings: Settings = Depends(app_settings)) -> SettingsRead:
    """Return the current tunable thresholds."""
    return SettingsRead(
        protection_timeout_minutes=settings.protection_timeout_minutes,
        loiter_threshold_seconds=settings.loiter_threshold_seconds,
        near_package_distance_px=settings.near_package_distance_px,
        frame_stride=settings.frame_stride,
        detection_conf_threshold=settings.detection_conf_threshold,
        incident_cooldown_seconds=settings.incident_cooldown_seconds,
        ring_mode=settings.ring_mode,
        llm_enabled=settings.llm_enabled,
    )


@router.put("", response_model=SettingsRead)
def update_settings(body: SettingsUpdate) -> SettingsRead:
    """Update tunable thresholds by setting environment variables and reloading.

    This persists in the process environment only; for permanent changes the user
    must update ``.env``.
    """
    import os  # noqa: PLC0415

    field_map = {
        "protection_timeout_minutes": "PROTECTION_TIMEOUT_MINUTES",
        "loiter_threshold_seconds": "LOITER_THRESHOLD_SECONDS",
        "near_package_distance_px": "NEAR_PACKAGE_DISTANCE_PX",
        "frame_stride": "FRAME_STRIDE",
        "detection_conf_threshold": "DETECTION_CONF_THRESHOLD",
        "incident_cooldown_seconds": "INCIDENT_COOLDOWN_SECONDS",
    }
    data = body.model_dump(exclude_none=True)
    for field_name, env_name in field_map.items():
        if field_name in data:
            os.environ[env_name] = str(data[field_name])
            logger.info("Setting updated %s=%s", env_name, data[field_name])

    settings = reload_settings()
    return SettingsRead(
        protection_timeout_minutes=settings.protection_timeout_minutes,
        loiter_threshold_seconds=settings.loiter_threshold_seconds,
        near_package_distance_px=settings.near_package_distance_px,
        frame_stride=settings.frame_stride,
        detection_conf_threshold=settings.detection_conf_threshold,
        incident_cooldown_seconds=settings.incident_cooldown_seconds,
        ring_mode=settings.ring_mode,
        llm_enabled=settings.llm_enabled,
    )
