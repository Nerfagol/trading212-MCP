"""Environment-only configuration for Trading 212."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class ConfigError(ValueError):
    """Raised when required server configuration is invalid."""


class Environment(StrEnum):
    """Official Trading 212 API environments."""

    DEMO = "demo"
    LIVE = "live"


_BASE_URLS = {
    Environment.DEMO: "https://demo.trading212.com/api/v0",
    Environment.LIVE: "https://live.trading212.com/api/v0",
}


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated credentials and environment selection."""

    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    environment: Environment = Environment.DEMO

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from the process environment or an explicit mapping."""
        values = os.environ if environ is None else environ
        api_key = values.get("T212_API_KEY", "")
        api_secret = values.get("T212_API_SECRET", "")
        if not api_key.strip() or not api_secret.strip():
            raise ConfigError("Trading 212 credentials are required")

        raw_environment = values.get("T212_ENV", Environment.DEMO.value).strip().lower()
        try:
            environment = Environment(raw_environment)
        except ValueError as exc:
            raise ConfigError("T212_ENV must be one of: demo, live") from exc

        return cls(api_key=api_key, api_secret=api_secret, environment=environment)

    @property
    def base_url(self) -> str:
        """Return the fixed official base URL for the selected environment."""
        return _BASE_URLS[self.environment]
