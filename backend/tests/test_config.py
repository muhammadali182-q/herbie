"""Configuration contract tests."""

import pytest
from pydantic import ValidationError

from herbie.config import Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "local"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert "localhost" in settings.database_url


def test_environment_values_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERBIE_ENVIRONMENT", "test")
    monkeypatch.setenv("HERBIE_API_PORT", "8123")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.api_port == 8123


def test_settings_are_immutable() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValidationError):
        setattr(settings, "api_port", 9000)  # noqa: B010 - exercise frozen runtime behavior
