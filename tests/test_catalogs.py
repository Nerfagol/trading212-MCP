from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from mcp import Client

from trading212_mcp.client import Trading212Client
from trading212_mcp.config import Settings
from trading212_mcp.server import create_server

INSTRUMENTS = [
    {"ticker": "AAA", "name": "An ABC fund", "isin": "US1", "currencyCode": "USD"},
    {"ticker": "ABC", "name": "Example", "isin": "US2", "currencyCode": "GBP"},
]


@pytest.mark.asyncio
async def test_search_prioritizes_exact_ticker_and_reuses_catalog() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=INSTRUMENTS)

    def factory() -> Trading212Client:
        return Trading212Client(Settings("synthetic", "synthetic"),
                                transport=httpx.MockTransport(respond))

    async with Client(create_server(factory)) as mcp:
        result = await mcp.call_tool("search_instruments", {"query": " abc ", "limit": 1})
        assert not result.is_error
        data = result.structured_content
        assert data is not None
        assert data["instruments"] == [INSTRUMENTS[1]]
        assert data["total_matches"] == 2
        assert data["truncated"] is True
        await mcp.call_tool("search_instruments", {"query": "US1"})
        invalid = await mcp.call_tool("search_instruments", {"query": " "})
        assert invalid.is_error
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v0/equity/metadata/instruments"


@pytest.mark.asyncio
async def test_pie_reads_have_fixed_get_routes_and_reject_invalid_ids() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"settings": {"id": 42}, "instruments": []})

    async with Trading212Client(Settings("synthetic", "synthetic"),
                                transport=httpx.MockTransport(respond)) as client:
        assert (await client.get_pie(42))["settings"] == {"id": 42}
        for value in [0, -1, True, 2**63]:
            with pytest.raises(ValueError):
                await client.get_pie(value)
        for path in ["/api/v0/equity/pies/42/duplicate", "/api/v0/equity/pies/01",
                     "/api/v0/equity/pies/42?write=true", "/api/v0/equity/pies/42#x"]:
            with pytest.raises(ValueError):
                await client._get_json(path)
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v0/equity/pies/42"


@pytest.mark.asyncio
async def test_catalog_expiry_concurrency_and_credential_isolation() -> None:
    from trading212_mcp.catalogs import MetadataCatalog

    now = [0.0]
    calls = 0
    status = 200

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return httpx.Response(status, json=INSTRUMENTS)

    catalog = MetadataCatalog(clock=lambda: now[0])
    async with Trading212Client(Settings("one", "synthetic"),
                                transport=httpx.MockTransport(respond)) as client:
        results = await asyncio.gather(*(catalog.read(client, "instruments") for _ in range(5)))
        assert results == [INSTRUMENTS] * 5
        assert calls == 1
        now[0] = 600
        status = 429
        from trading212_mcp.client import RateLimitError
        with pytest.raises(RateLimitError):
            await catalog.read(client, "instruments")
        status = 200
        assert await catalog.read(client, "instruments") == INSTRUMENTS
        assert calls == 3
    async with Trading212Client(Settings("two", "synthetic"),
                                transport=httpx.MockTransport(respond)) as client:
        await catalog.read(client, "instruments")
    assert calls == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "arguments", "payload", "key"), [
    ("get_exchanges", {}, [{"id": 1, "name": "Example", "workingSchedules": []}], "exchanges"),
    ("get_pies", {}, [], "pies"),
    ("get_pie", {"pie_id": 1}, {"settings": {"id": 1}, "instruments": []}, None),
])
async def test_new_reads_through_mcp(name: str, arguments: dict[str, Any],
                                   payload: Any, key: str | None) -> None:
    def factory() -> Trading212Client:
        return Trading212Client(Settings("synthetic", "synthetic"),
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    async with Client(create_server(factory)) as mcp:
        result = await mcp.call_tool(name, arguments)
    assert not result.is_error
    assert result.structured_content == ({key: payload} if key else payload)
