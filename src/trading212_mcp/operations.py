"""Bounded private logs containing only fixed operational events, never payloads."""

from __future__ import annotations

import json
import logging
import os
import stat
from datetime import UTC, datetime
from io import TextIOWrapper
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from trading212_mcp.snapshots import secure_directory

_EVENTS = {
    "mcp": {"starting", "stopped"},
    "collector": {"starting", "capture_succeeded", "capture_failed"},
}


class _PrivateHandler(RotatingFileHandler):
    def _open(self) -> TextIOWrapper[Any]:
        descriptor = os.open(
            self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
            | os.O_NONBLOCK, 0o600,
        )
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Invalid operational log file")
            os.fchmod(descriptor, 0o600)
            return os.fdopen(descriptor, "a", encoding="utf-8")
        except Exception:
            os.close(descriptor)
            raise

    def handleError(self, record: logging.LogRecord) -> None:
        raise OSError("Operational logging failed") from None


class OperationalLog:
    def __init__(self, component: str, directory: Path | None, *,
                 max_bytes: int = 1024 * 1024) -> None:
        if component not in _EVENTS or max_bytes < 1:
            raise ValueError("Invalid operational logging configuration")
        self.component = component
        self.logger = logging.Logger(f"trading212.{component}.operations", logging.INFO)
        self.handler: _PrivateHandler | None = None
        if directory is not None:
            with secure_directory(directory) as descriptor:
                info = os.fstat(descriptor)
                if info.st_mode & 0o077 or info.st_uid != os.getuid():
                    raise ValueError("Operational log directory must be private and runtime-owned")
            self.handler = _PrivateHandler(
                directory / f"{component}.jsonl", maxBytes=max_bytes, backupCount=2,
                encoding="utf-8",
            )
            self.logger.addHandler(self.handler)

    def emit(self, event: str) -> None:
        if event not in _EVENTS[self.component]:
            raise ValueError("Invalid operational event")
        self.logger.info(json.dumps({
            "timestamp": datetime.now(UTC).isoformat(),
            "component": self.component,
            "event": event,
        }))

    def close(self) -> None:
        if self.handler is not None:
            self.logger.removeHandler(self.handler)
            self.handler.close()
