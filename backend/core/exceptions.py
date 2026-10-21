"""Custom exceptions raised across porchPiracyAI.

All domain errors derive from :class:`PorchPiracyError` so the API layer can map
them onto HTTP status codes in one place.
"""


class PorchPiracyError(Exception):
    """Base class for every domain error raised by the application."""


class InvalidTransition(PorchPiracyError):
    """Raised when a protection state machine transition is not allowed."""

    def __init__(self, state: str, trigger: str) -> None:
        self.state = state
        self.trigger = trigger
        super().__init__(f"Invalid protection transition: {state} --{trigger}--> ?")


class ProtectionAlreadyActiveError(PorchPiracyError):
    """Raised when a second protection session is started while one is active."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Protection session already active: {session_id}")


class NoActiveProtectionError(PorchPiracyError):
    """Raised when an operation requires an active session and none exists."""

    def __init__(self, message: str = "No active protection session") -> None:
        super().__init__(message)


class NotFoundError(PorchPiracyError):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity: str, identifier: str) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class ValidationError(PorchPiracyError):
    """Raised when input violates a domain rule (not a schema rule)."""


class VisionDependencyError(PorchPiracyError):
    """Raised when the vision pipeline is used without its optional dependencies."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            "Vision pipeline dependencies are unavailable: "
            f"{detail}. Install them with `pip install -r requirements.txt`."
        )


class IntegrationError(PorchPiracyError):
    """Raised when an external integration (Ring, Telegram, Ollama) fails."""
