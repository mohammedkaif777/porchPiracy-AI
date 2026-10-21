"""porchPiracyAI — FastAPI application entry point.

Run with::

    python -m uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router
from backend.core.config import get_settings
from backend.core.db import create_db_and_tables
from backend.core.exceptions import (
    IntegrationError,
    InvalidTransition,
    NoActiveProtectionError,
    NotFoundError,
    PorchPiracyError,
    ProtectionAlreadyActiveError,
    ValidationError,
    VisionDependencyError,
)
from backend.core.logging_config import configure_logging, get_logger
from backend.schemas.system_schema import HealthResponse

logger = get_logger(__name__)

_STATUS_BY_ERROR: dict[type[PorchPiracyError], int] = {
    NotFoundError: 404,
    NoActiveProtectionError: 404,
    ProtectionAlreadyActiveError: 409,
    InvalidTransition: 400,
    ValidationError: 400,
    VisionDependencyError: 503,
    IntegrationError: 502,
}

_CODE_BY_ERROR: dict[type[PorchPiracyError], str] = {
    NotFoundError: "NOT_FOUND",
    NoActiveProtectionError: "NO_ACTIVE_PROTECTION",
    ProtectionAlreadyActiveError: "PROTECTION_ALREADY_ACTIVE",
    InvalidTransition: "INVALID_TRANSITION",
    ValidationError: "VALIDATION_ERROR",
    VisionDependencyError: "VISION_DEPENDENCY",
    IntegrationError: "INTEGRATION_ERROR",
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown hooks."""
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()
    create_db_and_tables()
    logger.info(
        "porchPiracyAI started version=%s debug=%s db=%s",
        settings.version,
        settings.debug,
        settings.database_url,
    )
    yield
    logger.info("porchPiracyAI shutting down")


settings = get_settings()

app = FastAPI(
    title="porchPiracyAI",
    version=settings.version,
    description="Package protection API: ingest events, run deterministic rules, notify the homeowner.",
    lifespan=lifespan,
)

# Wildcard origins cannot be combined with credentials; Streamlit is the only UI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PorchPiracyError)
async def handle_domain_error(_request: Request, exc: PorchPiracyError) -> JSONResponse:
    """Map domain errors onto the frozen ``{detail, code}`` error body."""
    status = _STATUS_BY_ERROR.get(type(exc), 400)
    code = _CODE_BY_ERROR.get(type(exc), "DOMAIN_ERROR")
    return JSONResponse(status_code=status, content={"detail": str(exc), "code": code})


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness probe used by the dashboard."""
    current = get_settings()
    return HealthResponse(status="ok", service="porchpiracyai", version=current.version)


app.include_router(router)
