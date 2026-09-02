"""Application configuration loaded from YAML + environment variables.

Non-secret operational settings come from config/settings.yaml.
Secrets and overrides come from environment variables / .env file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

# Project root is three levels up from this file: src/api/config.py -> src/api -> src -> project
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
_SETTINGS_FILE = _CONFIG_DIR / "settings.yaml"


def _load_yaml_settings() -> dict[str, Any]:
    """Load settings from the YAML configuration file."""
    if _SETTINGS_FILE.exists():
        with open(_SETTINGS_FILE) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    return {}


_yaml = _load_yaml_settings()
_app_yaml: dict[str, Any] = _yaml.get("app", {})
_server_yaml: dict[str, Any] = _yaml.get("server", {})


class Settings(BaseSettings):
    """Application settings with YAML defaults and environment variable overrides.

    Priority (highest to lowest):
    1. Environment variables
    2. .env file
    3. YAML config/settings.yaml
    4. Field defaults
    """

    # Application
    app_name: str = Field(default=_app_yaml.get("name", "REVIVE"))
    app_version: str = Field(default=_app_yaml.get("version", "0.1.0"))
    app_description: str = Field(
        default=_app_yaml.get("description", "Autonomous Revenue Recovery & Intervention Engine")
    )
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=_app_yaml.get("debug", False))

    # Server
    app_host: str = Field(default=_server_yaml.get("host", "0.0.0.0"))
    app_port: int = Field(default=_server_yaml.get("port", 8000))

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./data/revive_dev.db")
    database_echo: bool = Field(default=False)

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


def get_settings() -> Settings:
    """Create and return the application settings instance."""
    # Ensure .env file is loaded if it exists
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        # pydantic-settings handles .env loading through model_config
        pass
    return Settings()


# Module-level convenience — can be imported directly
settings = get_settings()
