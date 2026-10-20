from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from trading212_mcp.client import Trading212Client
from trading212_mcp.config import Settings

from .test_client import ACCOUNT, POSITION


@pytest.mark.asyncio
async def test_collector_captures_once_per_slot_across_restart(tmp_path: Path) -> None:
    from trading212_mcp.collector import SnapshotCollector
    from trading212_mcp.snapshots import SnapshotStore
    now = [datetime(2026, 10, 20, 8, 5, tzinfo=UTC)]
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=ACCOUNT if request.url.path.endswith("summary")
                              else [POSITION])
    def factory() -> Trading212Client:
        return Trading212Client(Settings("synthetic", "synthetic"),
                                transport=httpx.MockTransport(respond))
    store = SnapshotStore(tmp_path, "demo")
    collector = SnapshotCollector(store, factory, clock=lambda: now[0])
    await collector.poll()
    await collector.poll()
    restarted = SnapshotCollector(store, factory, clock=lambda: now[0])
    await restarted.poll()
    assert len(requests) == 2
    now[0] = datetime(2026, 10, 20, 20, 5, tzinfo=UTC)
    await restarted.poll()
    assert len(requests) == 4
    assert len(store.list()["snapshots"]) == 2
    assert all(request.method == "GET" for request in requests)


@pytest.mark.asyncio
async def test_failed_capture_waits_for_next_period_and_redacts_errors(tmp_path: Path) -> None:
    from trading212_mcp.collector import SnapshotCollector
    from trading212_mcp.snapshots import SnapshotStore
    now = [datetime(2026, 3, 29, 0, tzinfo=UTC)]
    calls = []
    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, text="SENSITIVE upstream body")
    def factory() -> Trading212Client:
        return Trading212Client(Settings("synthetic", "synthetic"),
                                transport=httpx.MockTransport(respond))
    store = SnapshotStore(tmp_path, "demo")
    collector = SnapshotCollector(store, factory, clock=lambda: now[0])
    await collector.poll()
    await collector.poll()
    assert len(calls) == 1
    assert collector.status()["state"] == "error"
    assert "SENSITIVE" not in str(collector.status())
    assert store.list()["snapshots"] == []
    now[0] = datetime(2026, 3, 29, 4, tzinfo=UTC)
    await collector.poll()
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_decimal_api_decoding_preserves_snapshot_precision() -> None:
    async with Trading212Client(Settings("synthetic", "synthetic"), decimal_json=True,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text='''[
            {"quantity": 0.1234567890123456789}]
        '''))) as client:
        result = await client.get_positions()
    assert result[0]["quantity"] == Decimal("0.1234567890123456789")


def test_health_checks_heartbeat_and_last_success() -> None:
    from trading212_mcp.collector import healthy
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    data: dict[str, Any] = {"heartbeat": "2026-10-20T12:00:00Z", "state": "ok",
                            "last_success": "2026-10-20T08:00:00Z"}
    assert healthy(data, now)
    assert not healthy(data | {"heartbeat": "2026-10-20T11:00:00Z"}, now)
    assert not healthy(data | {"last_success": "2026-10-19T08:00:00Z"}, now)
    assert not healthy(data | {"state": "error"}, now)
