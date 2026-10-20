"""Four-hour NAS snapshot collector, independent of MCP requests."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading212_mcp.client import Trading212Client
from trading212_mcp.config import Settings
from trading212_mcp.snapshots import SnapshotStore, parse_time, slot_start, timestamp

STATUS_PATH = Path("/tmp/trading212-collector-status.json")


def utc_now() -> datetime:
    return datetime.now(UTC)


class SnapshotCollector:
    """Attempt once per UTC period; only the collector can publish snapshots."""

    def __init__(self, store: SnapshotStore, factory: Callable[[], Trading212Client],
                 clock: Callable[[], datetime] = utc_now) -> None:
        self.store = store
        self.factory = factory
        self.clock = clock
        self._attempted: datetime | None = None
        self._last_success: str | None = None
        self._state = "starting"

    async def poll(self) -> None:
        started = self.clock()
        slot = slot_start(started)
        if self._attempted is not None and slot <= self._attempted:
            return
        self._attempted = slot
        try:
            with self.store.writer() as directory:
                if self.store.has_slot(directory, started):
                    self._last_success = self.store.list(limit=1)["snapshots"][0]["captured_at_utc"]
                else:
                    async with self.factory() as client:
                        account = await client.get_account()
                        positions = await client.get_positions()
                    completed = self.clock()
                    self.store.publish(directory, account, positions, started, completed)
                    self._last_success = timestamp(completed)
            self._state = "ok"
        except Exception:
            # No upstream text, filesystem paths, credentials or financial values in status/logs.
            self._state = "error"

    def status(self) -> dict[str, Any]:
        return {"heartbeat": timestamp(self.clock()), "state": self._state,
                "last_success": self._last_success,
                "last_attempt": timestamp(self._attempted) if self._attempted else None}


def healthy(data: dict[str, Any], now: datetime) -> bool:
    try:
        heartbeat_age = (now - parse_time(data["heartbeat"])).total_seconds()
        success_age = (now - parse_time(data["last_success"])).total_seconds()
        return data["state"] == "ok" and 0 <= heartbeat_age <= 120 and 0 <= success_age <= 28800
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def write_status(data: dict[str, Any]) -> None:
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=STATUS_PATH.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream)
        os.replace(temporary, STATUS_PATH)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


async def run() -> None:
    root = os.environ.get("T212_SNAPSHOT_DIR", "")
    if not root:
        raise ValueError("Snapshot storage is not configured")
    settings = Settings.from_env()
    collector = SnapshotCollector(SnapshotStore(Path(root), settings.environment.value),
                                  lambda: Trading212Client(settings, decimal_json=True))
    while True:
        await collector.poll()
        write_status(collector.status())
        await asyncio.sleep(30)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect private CSV snapshots every four hours")
    parser.add_argument("--health", action="store_true", help="Check local collector status only")
    args = parser.parse_args()
    if args.health:
        try:
            data = json.loads(STATUS_PATH.read_text())
            return 0 if isinstance(data, dict) and healthy(data, utc_now()) else 1
        except (OSError, ValueError):
            return 1
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Snapshot collector stopped; check configuration and storage", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
