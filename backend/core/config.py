"""Application settings, loaded from the environment and ``.env``.

Every tunable lives here. No module is allowed to hardcode a threshold or a
secret (see ``CLAUDE.md``, architecture rules).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the whole application.

    Values are read from the process environment first and from ``.env`` second.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---
    app_name: str = "porchPiracyAI"
    version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'porchpiracy.db'}"
    backend_url: str = "http://localhost:8000"

    # --- Storage ---
    data_dir: Path = PROJECT_ROOT / "data"
    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    annotated_dir: Path = PROJECT_ROOT / "data" / "annotated"
    evidence_dir: Path = PROJECT_ROOT / "data" / "evidence"
    samples_dir: Path = PROJECT_ROOT / "samples"
    models_dir: Path = PROJECT_ROOT / "models_weights"

    # --- Protection and threat thresholds ---
    protection_timeout_minutes: int = Field(default=360, ge=1)
    loiter_threshold_seconds: float = Field(default=8.0, ge=0.1)
    near_package_distance_px: float = Field(default=150.0, ge=1.0)
    interaction_iou_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    interaction_frames_required: int = Field(default=3, ge=1)
    package_movement_px: float = Field(default=60.0, ge=1.0)
    package_removed_seconds: float = Field(default=3.0, ge=0.1)
    incident_cooldown_seconds: float = Field(default=30.0, ge=0.0)
    event_cooldown_seconds: float = Field(default=2.0, ge=0.0)

    # --- Vision pipeline ---
    frame_stride: int = Field(default=2, ge=1)
    detection_conf_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    person_model_path: Path = PROJECT_ROOT / "models_weights" / "yolov8n.pt"
    package_model_path: Path = PROJECT_ROOT / "models_weights" / "package.pt"
    coco_package_proxy_classes: tuple[str, ...] = ("suitcase", "handbag", "backpack")
    annotated_fps_fallback: int = 25

    # --- Ring integration ---
    ring_mode: Literal["local", "real"] = "local"
    ring_client_id: str = ""
    ring_client_secret: str = ""
    ring_token: str = ""
    ring_base_url: str = ""

    # --- Local LLM (explanations only) ---
    llm_enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout_seconds: float = 20.0

    # --- Optional Telegram notifier ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # --- Dashboard ---
    use_mock: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ring_simulated(self) -> bool:
        """True when the Ring integration runs on the local development adapter."""
        return self.ring_mode != "real"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def telegram_enabled(self) -> bool:
        """True when both Telegram credentials are configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def ensure_directories(self) -> None:
        """Create the local storage directories if they do not exist yet."""
        for path in (self.data_dir, self.uploads_dir, self.annotated_dir, self.evidence_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    @property
    def mock_events_path(self) -> Path:
        """Path of the mock event stream used by the demo and the tests."""
        return self.samples_dir / "mock_events.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


def reload_settings() -> Settings:
    """Drop the cache and re-read the environment. Used after a settings update."""
    get_settings.cache_clear()
    return get_settings()
