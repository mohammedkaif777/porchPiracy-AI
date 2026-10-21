"""porchPiracyAI — FastAPI application entry point.

Run with::

    python -m uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

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
    ProtectionAlreadyActiveError,
    ValidationError,
    VisionDependencyError,
)
from backend.core.logging_config import configure_logging, get_logger
from backend.schemas.system_schema import HealthResponse

logger = get_logger(__name__)


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
    description="AI-powered porch piracy detection and prevention system.",
    lifespan=lifespan,
)

# CORS — allow the Streamlit dashboard and local dev origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------- exception handlers


@app.exception_handler(NotFoundError)
async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ProtectionAlreadyActiveError)
async def _already_active(_request: Request, exc: ProtectionAlreadyActiveError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(NoActiveProtectionError)
async def _no_active(_request: Request, exc: NoActiveProtectionError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidTransition)
async def _invalid_transition(_request: Request, exc: InvalidTransition) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def _validation(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(VisionDependencyError)
async def _vision_dep(_request: Request, exc: VisionDependencyError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IntegrationError)
async def _integration(_request: Request, exc: IntegrationError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


# ----------------------------------------------------------------- health check


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Simple health check."""
    return HealthResponse(version=settings.version)


# ----------------------------------------------------------------- routes

app.include_router(router)
