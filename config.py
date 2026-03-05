"""Application configuration loaded from .env via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    gtmetrix_api_key: str
    gtmetrix_default_location: str | None = None
    gtmetrix_default_browser: str | None = None
    gtmetrix_default_device: str | None = None
    gtmetrix_default_adblock: str | None = None


settings = Settings()
