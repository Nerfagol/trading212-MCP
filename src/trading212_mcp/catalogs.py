"""Short-lived, credential-isolated catalog cache; never stores financial responses."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from copy import deepcopy
from typing import Literal

from trading212_mcp.client import JsonList, Trading212Client


class MetadataCatalog:
    """Own a bounded cache for one server, sharing concurrent refreshes."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = asyncio.Lock()
        self._namespace: bytes | None = None
        self._entries: dict[str, tuple[float, JsonList]] = {}

    async def read(
        self, client: Trading212Client, kind: Literal["instruments", "exchanges"]
    ) -> JsonList:
        async with self._lock:
            if self._namespace != client.metadata_namespace:
                self._entries.clear()
                self._namespace = client.metadata_namespace
            entry = self._entries.get(kind)
            if entry is not None and self._clock() < entry[0]:
                return deepcopy(entry[1])
            data = (await client.get_instruments() if kind == "instruments"
                    else await client.get_exchanges())
            self._entries[kind] = (self._clock() + 600, deepcopy(data))
            return data


def search_instruments(items: JsonList, query: str, limit: int) -> dict[str, object]:
    """Search a catalog without introducing upstream query parameters."""
    query = query.strip().casefold()
    if not query or len(query) > 100 or not 1 <= limit <= 50:
        raise ValueError("Invalid instrument search")
    matches = [item for item in items if any(
        query in str(item.get(field, "")).casefold() for field in ("ticker", "name", "isin")
    )]
    matches.sort(key=lambda item: (
        not any(query == str(item.get(field, "")).casefold() for field in ("ticker", "isin")),
        str(item.get("ticker", "")),
    ))
    return {"instruments": matches[:limit], "total_matches": len(matches),
            "truncated": len(matches) > limit}
