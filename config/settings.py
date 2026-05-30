"""
settings.py — All environment-driven configuration in one place.

Loaded once at startup via pydantic-settings. Inject the resulting
`Settings` instance everywhere instead of calling `os.getenv()` from
scattered locations.

Usage::

    from config.settings import get_settings
    settings = get_settings()
    api_key = settings.sarvam_api_key
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root = the parent directory of `config/` (i.e. the repo root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Environment-driven configuration."""

    # ── Sarvam credentials & endpoints ──────────────────────────────
    sarvam_api_key: str = Field(
        default="",
        description="Sarvam AI subscription key. Get one from https://dashboard.sarvam.ai",
    )
    sarvam_base_url: str = Field(
        default="https://api.sarvam.ai",
        description="Sarvam AI REST base URL. Override only for sandboxes.",
    )

    # ── Output directories ──────────────────────────────────────────
    output_dir: Path = Field(
        default=_PROJECT_ROOT / "output",
        description="Directory where reports / resumes / profile JSON files are saved.",
    )

    # ── Logging ─────────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Python logging level (DEBUG / INFO / WARNING / ERROR).",
    )

    # ── pydantic-settings config ────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Lower-case attribute names map to the equivalent UPPER_SNAKE_CASE
        # environment variables automatically (SARVAM_API_KEY, LOG_LEVEL, …).
        extra="ignore",
    )

    @property
    def temp_audio_dir(self) -> Path:
        """Sub-directory for transient TTS/STT WAV files."""
        return self.output_dir / "temp"

    @property
    def debug_dir(self) -> Path:
        """Sub-directory where raw LLM responses are persisted for inspection."""
        return self.output_dir / "debug"

    def ensure_dirs(self) -> None:
        """Create output directories if they do not already exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_audio_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide singleton of the Settings object.

    The lru_cache means the `.env` file is parsed exactly once per
    Python interpreter run; subsequent calls return the same instance.
    """
    settings = Settings()
    settings.ensure_dirs()
    return settings
