from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from .test_client import ACCOUNT, POSITION

START = datetime(2026, 10, 20, 8, 0, 1, tzinfo=UTC)
END = datetime(2026, 10, 20, 8, 0, 2, tzinfo=UTC)


def publish(root: Path, positions: list[dict[str, Any]] | None = None,
            account: dict[str, Any] | None = None, end: datetime = END) -> str:
    from trading212_mcp.snapshots import SnapshotStore
    store = SnapshotStore(root, "demo")
    with store.writer() as directory:
        return store.publish(directory, account or ACCOUNT,
                             [POSITION] if positions is None else positions,
                             end - timedelta(seconds=1), end)


def test_two_csv_tables_preserve_decimals_and_return_complete_summary(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotStore
    position = POSITION | {"quantity": Decimal("0.1234567890123456789")}
    identifier = publish(tmp_path, [position])
    directory = tmp_path / "demo" / identifier
    assert sorted(p.name for p in directory.iterdir()) == ["positions.csv", "summary.csv"]
    with (directory / "positions.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["quantity"] == "0.1234567890123456789"
    assert rows[0]["price_currency"] == "USD"
    store = SnapshotStore(tmp_path, "demo")
    result = store.get(identifier)
    assert result["summary"]["total_account_value"] == "15250.75"
    assert result["summary"]["account_currency"] == "GBP"
    assert result["summary"]["captured_at_london"] == "2026-10-20T09:00:02+01:00"
    assert result["positions"][0]["quantity"] == rows[0]["quantity"]
    assert result["next_offset"] is None
    assert (directory / "positions.csv").stat().st_mode & 0o777 == 0o600


def test_empty_portfolio_still_creates_a_snapshot(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotStore
    identifier = publish(tmp_path, [])
    data = SnapshotStore(tmp_path, "demo").get(identifier)
    assert data["summary"]["position_count"] == 0
    assert data["positions"] == []


def test_snapshot_pages_filters_and_stable_cursor(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotStore
    instrument = cast(dict[str, Any], POSITION["instrument"])
    first = publish(tmp_path, [POSITION, POSITION | {
        "instrument": instrument | {"ticker": "ZZZ", "name": "Other"}}])
    second = publish(tmp_path, end=datetime(2026, 10, 20, 12, 0, 2, tzinfo=UTC))
    store = SnapshotStore(tmp_path, "demo")
    page = store.list(limit=1)
    assert page["snapshots"][0]["snapshot_id"] == second
    assert store.list(cursor=page["next_cursor"])["snapshots"][0]["snapshot_id"] == first
    assert store.list(start="2026-10-20T10:00:00Z")["snapshots"][0]["snapshot_id"] == second
    data = store.get(first, limit=1)
    assert data["next_offset"] == 1
    assert store.get(first, offset=1)["positions"][0]["ticker"] == "ZZZ"
    with pytest.raises(ValueError):
        store.list(start="2026-10-20")


def test_reject_mixed_accounts_invalid_values_and_duplicate_slot(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotError, SnapshotStore
    publish(tmp_path)
    with pytest.raises(SnapshotError):
        publish(tmp_path, account=ACCOUNT | {"id": 999})
    with pytest.raises(SnapshotError):
        publish(tmp_path)
    with pytest.raises(SnapshotError):
        publish(tmp_path, [POSITION | {"currentPrice": float("nan")}],
                end=datetime(2026, 10, 20, 12, tzinfo=UTC))
    assert len(SnapshotStore(tmp_path, "demo").list()["snapshots"]) == 1
    assert SnapshotStore(tmp_path, "live").list()["snapshots"] == []


def test_snapshot_reader_refuses_paths_symlinks_and_corruption(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotError, SnapshotStore
    identifier = publish(tmp_path)
    store = SnapshotStore(tmp_path, "demo")
    for value in ["../summary.csv", "/etc/passwd", "20261020T080002000000Z/positions.csv"]:
        with pytest.raises((ValueError, SnapshotError)):
            store.get(value)
    path = tmp_path / "demo" / identifier / "positions.csv"
    path.unlink()
    path.symlink_to(tmp_path / "demo" / identifier / "summary.csv")
    with pytest.raises(SnapshotError):
        store.get(identifier)
    path.unlink()
    path.write_text("not,a,snapshot\n")
    with pytest.raises(SnapshotError):
        store.get(identifier)


def test_lock_and_failed_publish_do_not_expose_partial_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading212_mcp.snapshots import SnapshotError, SnapshotStore
    store = SnapshotStore(tmp_path, "demo")
    with store.writer(), pytest.raises(SnapshotError), store.writer():
        pass
    def full(*args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic disk full")
    monkeypatch.setattr("trading212_mcp.snapshots.os.rename", full)
    with pytest.raises(SnapshotError):
        publish(tmp_path)
    assert store.list()["snapshots"] == []


def test_csv_formula_text_is_safe_and_round_trips(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotStore
    position = POSITION | {
        "instrument": cast(dict[str, Any], POSITION["instrument"]) | {"name": "=1+1"}}
    identifier = publish(tmp_path, [position])
    content = (tmp_path / "demo" / identifier / "positions.csv").read_text()
    assert "'=1+1" in content
    assert SnapshotStore(tmp_path, "demo").get(identifier)["positions"][0]["name"] == "=1+1"


def test_missing_summary_or_account_binding_is_not_silently_ignored(tmp_path: Path) -> None:
    from trading212_mcp.snapshots import SnapshotError, SnapshotStore
    identifier = publish(tmp_path)
    (tmp_path / "demo" / ".account").unlink()
    with pytest.raises(SnapshotError):
        publish(tmp_path, account=ACCOUNT | {"id": 999}, end=END + timedelta(hours=4))
    (tmp_path / "demo" / identifier / "summary.csv").unlink()
    with pytest.raises(SnapshotError):
        SnapshotStore(tmp_path, "demo").list()


def test_final_sync_failure_preserves_published_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from trading212_mcp.snapshots import SnapshotError, SnapshotStore
    sync = os.fsync
    store = SnapshotStore(tmp_path, "demo")
    with store.writer() as directory:
        def fail_final(fd: int) -> None:
            if fd == directory:
                raise OSError("synthetic sync failure")
            sync(fd)
        monkeypatch.setattr(os, "fsync", fail_final)
        with pytest.raises(SnapshotError):
            store.publish(directory, ACCOUNT, [POSITION], START, END)
    identifier = END.strftime("%Y%m%dT%H%M%S%fZ")
    assert store.get(identifier)["summary"]["position_count"] == 1
