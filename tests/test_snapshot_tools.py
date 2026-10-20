from pathlib import Path

import pytest
from mcp import Client

from trading212_mcp.server import create_server

from .test_snapshots import publish


@pytest.mark.asyncio
async def test_snapshot_tools_read_saved_tables_without_api_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    identifier = publish(tmp_path)
    monkeypatch.setenv("T212_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setenv("T212_ENV", " DEMO ")
    monkeypatch.delenv("T212_API_KEY", raising=False)
    monkeypatch.delenv("T212_API_SECRET", raising=False)
    server = create_server()
    async with Client(server) as client:
        listing = await client.call_tool("list_snapshots", {})
        result = await client.call_tool("get_snapshot", {"snapshot_id": identifier})
    assert not listing.is_error
    assert not result.is_error
    assert listing.structured_content is not None
    assert listing.structured_content["snapshots"][0]["snapshot_id"] == identifier
    assert result.structured_content is not None
    assert result.structured_content["positions"][0]["ticker"] == "AAPL_US_EQ"


@pytest.mark.asyncio
async def test_unconfigured_snapshots_are_discoverable_but_fail_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("T212_SNAPSHOT_DIR", raising=False)
    async with Client(create_server()) as client:
        result = await client.call_tool("list_snapshots", {})
    assert result.is_error
    assert "snapshot storage is not configured" in str(result.content).lower()
