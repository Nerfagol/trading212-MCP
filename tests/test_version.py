from __future__ import annotations

import importlib
import importlib.metadata
import tomllib
from pathlib import Path

import httpx
import pytest

import trading212_mcp
import trading212_mcp.client as client_module
import trading212_mcp.server as server_module
from trading212_mcp.config import Environment, Settings

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as pyproject:
        return str(tomllib.load(pyproject)["project"]["version"])


def test_package_version_comes_from_installed_distribution_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_distributions: list[str] = []

    def fake_version(distribution_name: str) -> str:
        requested_distributions.append(distribution_name)
        return "9.8.7"

    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    try:
        reloaded = importlib.reload(trading212_mcp)

        assert reloaded.__version__ == "9.8.7"
        assert requested_distributions == ["trading212-mcp"]
    finally:
        monkeypatch.undo()
        importlib.reload(trading212_mcp)


def test_installed_package_version_matches_pyproject() -> None:
    assert importlib.metadata.version("trading212-mcp") == project_version()
    assert trading212_mcp.__version__ == project_version()


def test_mcp_server_uses_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_module, "__version__", "9.8.7", raising=False)

    assert server_module.create_server().version == "9.8.7"


@pytest.mark.asyncio
async def test_http_user_agent_uses_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_user_agent = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_user_agent
        observed_user_agent = request.headers["User-Agent"]
        return httpx.Response(
            200,
            json={
                "id": 1,
                "currency": "GBP",
                "totalValue": 0,
                "cash": {
                    "availableToTrade": 0,
                    "reservedForOrders": 0,
                    "inPies": 0,
                },
                "investments": {
                    "currentValue": 0,
                    "totalCost": 0,
                    "realizedProfitLoss": 0,
                    "unrealizedProfitLoss": 0,
                },
            },
        )

    monkeypatch.setattr(client_module, "__version__", "9.8.7", raising=False)
    settings = Settings(
        api_key="api-key",
        api_secret="api-secret",
        environment=Environment.DEMO,
    )
    async with client_module.Trading212Client(
        settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        await client.get_account()

    assert observed_user_agent == "trading212-mcp/9.8.7"
