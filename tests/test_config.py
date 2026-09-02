"""Tests for application configuration loading."""

from __future__ import annotations

from src.api.config import Settings, get_settings


class TestSettings:
    """Tests for the Settings configuration class."""

    def test_settings_loads_defaults(self) -> None:
        """Settings should load with valid defaults."""
        s = get_settings()
        assert s.app_name == "REVIVE"
        assert isinstance(s.app_version, str)
        assert len(s.app_version) > 0

    def test_settings_has_app_env(self) -> None:
        """Settings should have an environment field."""
        s = get_settings()
        assert isinstance(s.app_env, str)

    def test_settings_has_host_and_port(self) -> None:
        """Settings should have host and port for the server."""
        s = get_settings()
        assert isinstance(s.app_host, str)
        assert isinstance(s.app_port, int)
        assert s.app_port > 0

    def test_settings_is_pydantic_model(self) -> None:
        """Settings should be a Pydantic BaseSettings instance."""
        s = get_settings()
        assert isinstance(s, Settings)
