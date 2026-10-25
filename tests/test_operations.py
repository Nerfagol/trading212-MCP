from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading212_mcp.operations import OperationalLog


def test_log_accepts_only_fixed_events_and_private_files(tmp_path: Path) -> None:
    log = OperationalLog("collector", tmp_path)
    log.emit("capture_succeeded")
    with pytest.raises(ValueError):
        log.emit("secret or portfolio value")
    log.close()
    path = tmp_path / "collector.jsonl"
    row = json.loads(path.read_text())
    assert set(row) == {"timestamp", "component", "event"}
    assert row["component"] == "collector"
    assert row["event"] == "capture_succeeded"
    assert path.stat().st_mode & 0o777 == 0o600


def test_logs_rotate_with_bounded_retention(tmp_path: Path) -> None:
    log = OperationalLog("mcp", tmp_path, max_bytes=200)
    for _ in range(20):
        log.emit("starting")
    log.close()
    assert (tmp_path / "mcp.jsonl.2").is_file()
    assert not (tmp_path / "mcp.jsonl.3").exists()
    assert all(p.stat().st_size < 400 for p in tmp_path.glob("mcp.jsonl*"))


def test_log_rejects_symlinks_and_public_directories(tmp_path: Path) -> None:
    target = tmp_path / "untouched"
    target.write_text("sentinel")
    (tmp_path / "mcp.jsonl").symlink_to(target)
    with pytest.raises(OSError):
        OperationalLog("mcp", tmp_path)
    assert target.read_text() == "sentinel"
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        OperationalLog("collector", tmp_path)
