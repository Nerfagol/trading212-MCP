"""Private, atomic CSV snapshots. Readers never write or contact Trading 212."""

from __future__ import annotations

import csv
import fcntl
import hashlib
import os
import re
import stat
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SUMMARY = ("schema_version", "snapshot_id", "scheduled_for_utc", "capture_started_at_utc",
           "captured_at_utc", "environment", "account_currency", "total_account_value",
           "position_count")
POSITIONS = ("snapshot_id", "ticker", "name", "quantity", "current_price", "price_currency")
ID_PATTERN = re.compile(r"[0-9]{8}T[0-9]{12}Z")
MAX_FILE_BYTES = 32 * 1024 * 1024


class SnapshotError(ValueError):
    """Safe error suitable for MCP or operational status."""


def timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SnapshotError("Timestamp must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        timestamp(result)
        return result.astimezone(UTC)
    except (ValueError, OverflowError):
        raise SnapshotError("Invalid timezone-aware timestamp") from None


def slot_start(value: datetime) -> datetime:
    value = parse_time(timestamp(value))
    return value.replace(hour=value.hour // 4 * 4, minute=0, second=0, microsecond=0)


def decimal_text(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise SnapshotError("Invalid snapshot numeric data")
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result.adjusted()) > 1000:
            raise InvalidOperation
        return format(result, "f")
    except (InvalidOperation, ValueError):
        raise SnapshotError("Invalid snapshot numeric data") from None


def _text(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        raise SnapshotError("Invalid snapshot text data")
    return value


def _csv_text(value: str) -> str:
    # Escape apostrophes too so the transformation is reversible for MCP reads.
    if value.startswith(("'", "\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _identifier(value: str) -> str:
    if not ID_PATTERN.fullmatch(value):
        raise SnapshotError("Invalid snapshot identifier")
    try:
        datetime.strptime(value, "%Y%m%dT%H%M%S%fZ")
    except ValueError:
        raise SnapshotError("Invalid snapshot identifier") from None
    return value


@contextmanager
def secure_directory(path: Path) -> Iterator[int]:
    """Walk directories with no-follow opens, including all parent components."""
    if ".." in path.parts:
        raise SnapshotError("Invalid snapshot storage path")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.absolute().parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _open_file(directory: int, name: str) -> int:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES or info.st_nlink != 1:
        os.close(fd)
        raise SnapshotError("Invalid snapshot file")
    return fd


def _read_csv(directory: int, name: str, fields: Sequence[str]) -> list[dict[str, str]]:
    with os.fdopen(_open_file(directory, name), encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(fields):
            raise SnapshotError("Invalid snapshot schema")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise SnapshotError("Invalid snapshot row")
            rows.append({key: value[1:] if value.startswith("'") else value
                         for key, value in row.items()})
        return rows


def _write_csv(directory: int, name: str, fields: Sequence[str],
               rows: Sequence[dict[str, str]]) -> None:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                 dir_fd=directory)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: _csv_text(value) for key, value in row.items()} for row in rows)
        stream.flush()
        if os.fstat(stream.fileno()).st_size > MAX_FILE_BYTES:
            raise SnapshotError("Snapshot exceeds file size limit")
        os.fsync(stream.fileno())


class SnapshotStore:
    """One configured store, separated by environment and bound to an account."""

    def __init__(self, root: Path, environment: str) -> None:
        if environment not in {"demo", "live"}:
            raise SnapshotError("Invalid snapshot environment")
        self.root = root
        self.environment = environment

    @contextmanager
    def writer(self) -> Iterator[int]:
        """Hold the environment lock across API reads and atomic publication."""
        try:
            with secure_directory(self.root) as root:
                with suppress(FileExistsError):
                    os.mkdir(self.environment, 0o700, dir_fd=root)
                directory = os.open(self.environment, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=root)
            try:
                lock = os.open(".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                               0o600, dir_fd=directory)
                try:
                    if not stat.S_ISREG(os.fstat(lock).st_mode) or os.fstat(lock).st_nlink != 1:
                        raise SnapshotError("Invalid snapshot lock")
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    yield directory
                finally:
                    os.close(lock)
            finally:
                os.close(directory)
        except OSError:
            raise SnapshotError("Snapshot storage is unavailable or busy") from None

    def _summary(self, directory: int, identifier: str) -> dict[str, Any]:
        rows = _read_csv(directory, "summary.csv", SUMMARY)
        if len(rows) != 1:
            raise SnapshotError("Invalid snapshot summary")
        row = rows[0]
        if (row["schema_version"] != "1" or row["snapshot_id"] != identifier
                or row["environment"] != self.environment):
            raise SnapshotError("Invalid snapshot summary")
        started = parse_time(row["capture_started_at_utc"])
        captured = parse_time(row["captured_at_utc"])
        if (captured < started or captured.strftime("%Y%m%dT%H%M%S%fZ") != identifier
                or parse_time(row["scheduled_for_utc"]) != slot_start(started)):
            raise SnapshotError("Invalid snapshot timestamps")
        count = int(row["position_count"])
        if count < 0:
            raise SnapshotError("Invalid snapshot position count")
        return dict(row) | {
            "position_count": count,
            "account_currency": _text(row["account_currency"]),
            "total_account_value": decimal_text(row["total_account_value"]),
            "captured_at_london": captured.astimezone(ZoneInfo("Europe/London")).isoformat(),
        }

    def _summaries(self, directory: int) -> list[dict[str, Any]]:
        result = []
        for name in sorted(os.listdir(directory), reverse=True):
            if not ID_PATTERN.fullmatch(name):
                continue
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            try:
                result.append(self._summary(child, _identifier(name)))
            finally:
                os.close(child)
        return result

    def has_slot(self, directory: int, time: datetime) -> bool:
        expected = timestamp(slot_start(time))
        return any(row["scheduled_for_utc"] == expected for row in self._summaries(directory))

    def publish(self, directory: int, account: dict[str, Any], positions: list[dict[str, Any]],
                started: datetime, completed: datetime) -> str:
        """Publish both CSVs together. Caller must hold writer()."""
        try:
            identifier = completed.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            if completed < started:
                raise SnapshotError("Invalid snapshot timestamps")
            account_id = account.get("id")
            if type(account_id) is not int:
                raise SnapshotError("Invalid snapshot account identity")
            fingerprint = hashlib.sha256(f"{self.environment}:{account_id}".encode()).hexdigest()
            rows = [{"snapshot_id": identifier,
                     "ticker": _text(position["instrument"]["ticker"]),
                     "name": _text(position["instrument"]["name"]),
                     "quantity": decimal_text(position["quantity"]),
                     "current_price": decimal_text(position["currentPrice"]),
                     "price_currency": _text(position["instrument"]["currency"])}
                    for position in positions]
            rows.sort(key=lambda row: row["ticker"])
            summary = {"schema_version": "1", "snapshot_id": identifier,
                       "scheduled_for_utc": timestamp(slot_start(started)),
                       "capture_started_at_utc": timestamp(started),
                       "captured_at_utc": timestamp(completed), "environment": self.environment,
                       "account_currency": _text(account["currency"]),
                       "total_account_value": decimal_text(account["totalValue"]),
                       "position_count": str(len(rows))}
            try:
                with os.fdopen(_open_file(directory, ".account")) as stream:
                    if stream.read() != fingerprint:
                        raise SnapshotError("Snapshot directory belongs to another account")
            except FileNotFoundError:
                if any(ID_PATTERN.fullmatch(name) for name in os.listdir(directory)):
                    raise SnapshotError("Snapshot account binding is missing") from None
                fd = os.open(".account", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
                with os.fdopen(fd, "w") as stream:
                    stream.write(fingerprint)
                    stream.flush()
                    os.fsync(stream.fileno())
            if self.has_slot(directory, started):
                raise SnapshotError("This snapshot period is already captured")
            temporary = ".pending-" + uuid.uuid4().hex
            os.mkdir(temporary, 0o700, dir_fd=directory)
            child = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            published = False
            try:
                _write_csv(child, "summary.csv", SUMMARY, [summary])
                _write_csv(child, "positions.csv", POSITIONS, rows)
                os.fsync(child)
                os.rename(temporary, identifier, src_dir_fd=directory, dst_dir_fd=directory)
                published = True
                os.fsync(directory)
            except BaseException:
                if not published:
                    for name in ("summary.csv", "positions.csv"):
                        with suppress(OSError):
                            os.unlink(name, dir_fd=child)
                    with suppress(OSError):
                        os.rmdir(temporary, dir_fd=directory)
                raise
            finally:
                os.close(child)
            return identifier
        except (OSError, KeyError, TypeError, UnicodeError, csv.Error):
            raise SnapshotError("Unable to save a complete snapshot") from None

    def list(self, *, start: str | None = None, end: str | None = None,
             cursor: str | None = None, limit: int = 20) -> dict[str, Any]:
        if not 1 <= limit <= 50:
            raise SnapshotError("Snapshot limit must be between 1 and 50")
        lower = parse_time(start) if start else None
        upper = parse_time(end) if end else None
        if lower and upper and lower > upper:
            raise SnapshotError("Snapshot date range is reversed")
        if cursor is not None:
            _identifier(cursor)
        try:
            with secure_directory(self.root / self.environment) as directory:
                try:
                    rows = self._summaries(directory)
                except FileNotFoundError:
                    raise SnapshotError("Incomplete snapshot history") from None
            matches = [row for row in rows if
                       (lower is None or parse_time(row["captured_at_utc"]) >= lower)
                       and (upper is None or parse_time(row["captured_at_utc"]) <= upper)
                       and (cursor is None or row["snapshot_id"] < cursor)]
            page = matches[:limit]
            return {"snapshots": page,
                    "next_cursor": page[-1]["snapshot_id"] if len(matches) > limit else None}
        except FileNotFoundError:
            return {"snapshots": [], "next_cursor": None}
        except (OSError, ValueError, UnicodeError, csv.Error):
            raise SnapshotError("Unable to read snapshot history") from None

    def get(self, identifier: str, *, offset: int = 0, limit: int = 100) -> dict[str, Any]:
        _identifier(identifier)
        if offset < 0 or not 1 <= limit <= 200:
            raise SnapshotError("Invalid snapshot page")
        try:
            with secure_directory(self.root / self.environment / identifier) as directory:
                summary = self._summary(directory, identifier)
                rows = _read_csv(directory, "positions.csv", POSITIONS)
            if len(rows) != summary["position_count"]:
                raise SnapshotError("Incomplete snapshot")
            for row in rows:
                if row["snapshot_id"] != identifier:
                    raise SnapshotError("Mismatched snapshot identifier")
                for key in ("ticker", "name", "price_currency"):
                    _text(row[key])
                for key in ("quantity", "current_price"):
                    row[key] = decimal_text(row[key])
            return {"summary": summary, "positions": rows[offset:offset + limit],
                    "next_offset": offset + limit if offset + limit < len(rows) else None}
        except FileNotFoundError:
            raise SnapshotError("Snapshot not found") from None
        except (OSError, ValueError, UnicodeError, csv.Error):
            raise SnapshotError("Unable to read complete snapshot") from None
