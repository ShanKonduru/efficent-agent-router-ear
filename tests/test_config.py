"""Tests for ear.config — configuration loading and validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ear.config import EARConfig, get_config


class TestEARConfig:
    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
        config = EARConfig()  # type: ignore[call-arg]
        assert config.openrouter_api_key == "sk-or-test-key"

    def test_defaults_are_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
        config = EARConfig()  # type: ignore[call-arg]
        assert config.ear_registry_ttl_seconds == 300
        assert config.ear_default_budget == "medium"
        assert config.ear_max_retries == 3
        assert config.ear_request_timeout_seconds == 30
        assert config.ear_openrouter_base_url == "https://openrouter.ai/api/v1"

    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        # Override env_file to a non-existent path so pydantic-settings cannot
        # fall back to reading the real .env file during this test.
        with pytest.raises(ValidationError):
            EARConfig(_env_file=str(tmp_path / ".env.nonexistent"))  # type: ignore[call-arg]

    def test_get_config_returns_ear_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
        config = get_config()
        assert isinstance(config, EARConfig)

    def test_custom_values_override_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-custom")
        monkeypatch.setenv("EAR_REGISTRY_TTL_SECONDS", "60")
        monkeypatch.setenv("EAR_MAX_RETRIES", "5")
        config = EARConfig()  # type: ignore[call-arg]
        assert config.ear_registry_ttl_seconds == 60
        assert config.ear_max_retries == 5
