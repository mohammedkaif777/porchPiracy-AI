"""Aggregate router that collects every route module."""

from fastapi import APIRouter

from backend.api.routes.event_routes import router as event_router
from backend.api.routes.incident_routes import router as incident_router
from backend.api.routes.integration_routes import router as integration_router
from backend.api.routes.protection_routes import router as protection_router
from backend.api.routes.settings_routes import router as settings_router
from backend.api.routes.simulate_routes import router as simulate_router
from backend.api.routes.video_routes import router as video_router

router = APIRouter()
router.include_router(video_router)
router.include_router(protection_router)
router.include_router(simulate_router)
router.include_router(event_router)
router.include_router(incident_router)
router.include_router(settings_router)
router.include_router(integration_router)

__all__ = ["router"]
