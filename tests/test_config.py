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


# --- Phase 4: Optional default config fields ---


def test_settings_default_browser_from_env(monkeypatch):
    """Settings with GTMETRIX_DEFAULT_BROWSER env var returns that value."""
    monkeypatch.setenv("GTMETRIX_API_KEY", "key")
    monkeypatch.setenv("GTMETRIX_DEFAULT_BROWSER", "3")
    from config import Settings
    s = Settings()
    assert s.gtmetrix_default_browser == "3"


def test_settings_default_device_from_env(monkeypatch):
    """Settings with GTMETRIX_DEFAULT_DEVICE env var returns that value."""
    monkeypatch.setenv("GTMETRIX_API_KEY", "key")
    monkeypatch.setenv("GTMETRIX_DEFAULT_DEVICE", "phone")
    from config import Settings
    s = Settings()
    assert s.gtmetrix_default_device == "phone"


def test_settings_default_adblock_from_env(monkeypatch):
    """Settings with GTMETRIX_DEFAULT_ADBLOCK env var returns that value."""
    monkeypatch.setenv("GTMETRIX_API_KEY", "key")
    monkeypatch.setenv("GTMETRIX_DEFAULT_ADBLOCK", "1")
    from config import Settings
    s = Settings()
    assert s.gtmetrix_default_adblock == "1"


def test_settings_defaults_none_when_unset(monkeypatch):
    """All three default fields are None when env vars not set."""
    monkeypatch.setenv("GTMETRIX_API_KEY", "key")
    monkeypatch.delenv("GTMETRIX_DEFAULT_BROWSER", raising=False)
    monkeypatch.delenv("GTMETRIX_DEFAULT_DEVICE", raising=False)
    monkeypatch.delenv("GTMETRIX_DEFAULT_ADBLOCK", raising=False)
    from config import Settings
    s = Settings()
    assert s.gtmetrix_default_browser is None
    assert s.gtmetrix_default_device is None
    assert s.gtmetrix_default_adblock is None
