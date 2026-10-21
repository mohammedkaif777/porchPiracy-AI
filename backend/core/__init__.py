"""Core layer: settings, database, logging and custom exceptions."""

from backend.core.config import Settings, get_settings, reload_settings
from backend.core.db import (
    create_db_and_tables,
    create_db_engine,
    get_engine,
    get_session,
    session_scope,
    set_engine,
)
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

__all__ = [
    "IntegrationError",
    "InvalidTransition",
    "NoActiveProtectionError",
    "NotFoundError",
    "PorchPiracyError",
    "ProtectionAlreadyActiveError",
    "Settings",
    "ValidationError",
    "VisionDependencyError",
    "configure_logging",
    "create_db_and_tables",
    "create_db_engine",
    "get_engine",
    "get_logger",
    "get_session",
    "get_settings",
    "reload_settings",
    "session_scope",
    "set_engine",
]
