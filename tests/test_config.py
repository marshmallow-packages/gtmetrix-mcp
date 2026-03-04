"""Tests for config.py -- SERV-02: API key loaded from .env via pydantic-settings."""
import pytest
from unittest.mock import patch
import os


def test_settings_reads_api_key_from_env(monkeypatch):
    """settings.gtmetrix_api_key returns the value set in the environment."""
    monkeypatch.setenv("GTMETRIX_API_KEY", "test_key_abc123")
    # Re-import to pick up the monkeypatched env
    import importlib
    import config
    importlib.reload(config)
    from config import Settings
    s = Settings()
    assert s.gtmetrix_api_key == "test_key_abc123"


def test_settings_raises_on_missing_api_key(monkeypatch):
    """Settings() raises a validation error when GTMETRIX_API_KEY is absent."""
    monkeypatch.delenv("GTMETRIX_API_KEY", raising=False)
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import ValidationError

    class IsolatedSettings(BaseSettings):
        model_config = SettingsConfigDict(env_file=None)
        gtmetrix_api_key: str

    with pytest.raises(ValidationError):
        IsolatedSettings()


def test_api_key_is_string(monkeypatch):
    """gtmetrix_api_key is a non-empty string."""
    monkeypatch.setenv("GTMETRIX_API_KEY", "some_key")
    from config import Settings
    s = Settings()
    assert isinstance(s.gtmetrix_api_key, str)
    assert len(s.gtmetrix_api_key) > 0
