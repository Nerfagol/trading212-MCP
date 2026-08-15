from __future__ import annotations

import pytest

from trading212_mcp.config import ConfigError, Environment, Settings


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"T212_API_KEY": "key-only"},
        {"T212_API_SECRET": "secret-only"},
        {"T212_API_KEY": "", "T212_API_SECRET": "secret"},
    ],
)
def test_settings_require_a_complete_non_empty_credential_pair(
    environ: dict[str, str],
) -> None:
    with pytest.raises(ConfigError, match="credentials are required"):
        Settings.from_env(environ)


@pytest.mark.parametrize(
    ("value", "expected_environment", "expected_url"),
    [
        ("demo", Environment.DEMO, "https://demo.trading212.com/api/v0"),
        (" DEMO ", Environment.DEMO, "https://demo.trading212.com/api/v0"),
        ("live", Environment.LIVE, "https://live.trading212.com/api/v0"),
        ("LIVE", Environment.LIVE, "https://live.trading212.com/api/v0"),
    ],
)
def test_settings_select_only_official_environments(
    value: str,
    expected_environment: Environment,
    expected_url: str,
) -> None:
    settings = Settings.from_env(
        {
            "T212_API_KEY": "example-key",
            "T212_API_SECRET": "example-secret",
            "T212_ENV": value,
        }
    )

    assert settings.environment is expected_environment
    assert settings.base_url == expected_url


def test_settings_default_to_demo_to_avoid_accidental_live_access() -> None:
    settings = Settings.from_env(
        {"T212_API_KEY": "example-key", "T212_API_SECRET": "example-secret"}
    )

    assert settings.environment is Environment.DEMO


def test_invalid_environment_error_redacts_credentials() -> None:
    key = "key-that-must-never-appear"
    secret = "secret-that-must-never-appear"

    with pytest.raises(ConfigError) as captured:
        Settings.from_env({"T212_API_KEY": key, "T212_API_SECRET": secret, "T212_ENV": "staging"})

    message = str(captured.value)
    assert "T212_ENV must be one of: demo, live" in message
    assert key not in message
    assert secret not in message


def test_settings_repr_redacts_credentials() -> None:
    settings = Settings.from_env(
        {"T212_API_KEY": "private-key", "T212_API_SECRET": "private-secret"}
    )

    rendered = repr(settings)
    assert "private-key" not in rendered
    assert "private-secret" not in rendered
