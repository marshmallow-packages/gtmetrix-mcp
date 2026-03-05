"""Application configuration loaded from environment variables via pydantic-settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        extra="ignore",
    )
    gtmetrix_api_key: str
    gtmetrix_default_location: str | None = None
    gtmetrix_default_browser: str | None = None
    gtmetrix_default_device: str | None = None
    gtmetrix_default_adblock: str | None = None


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton, creating it on first access."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
