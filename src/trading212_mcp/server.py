"""MCP Streamable HTTP server exposing only read-only Trading 212 tools."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Annotated, Any, TypeVar

import uvicorn
from mcp import types
from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from trading212_mcp import __version__
from trading212_mcp.catalogs import MetadataCatalog
from trading212_mcp.catalogs import search_instruments as search_catalog
from trading212_mcp.client import Trading212Client, Trading212Error
from trading212_mcp.config import ConfigError, Settings
from trading212_mcp.snapshots import SnapshotError, SnapshotStore

ClientFactory = Callable[[], Trading212Client]
T = TypeVar("T")

Limit = Annotated[
    int,
    Field(
        ge=1,
        le=50,
        description="Number of items in this page. Trading 212 permits 1 through 50.",
    ),
]
Ticker = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        description="Exact Trading 212 instrument ticker, such as AAPL_US_EQ.",
    ),
]
NextPagePath = Annotated[
    str,
    Field(
        max_length=2048,
        description="Exact next_page_path returned by the preceding call to this same tool.",
    ),
]

_READ_ONLY_ANNOTATIONS = types.ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=False,
)

_DEFAULT_ALLOWED_HOSTS = "127.0.0.1:*,localhost:*,[::1]:*,trading212-mcp:*"
_DEFAULT_ALLOWED_ORIGINS = "http://127.0.0.1:*,http://localhost:*,http://[::1]:*"

_TOOL_ARGUMENTS = {
    "get_account": frozenset(),
    "get_cash": frozenset(),
    "get_portfolio": frozenset(),
    "get_position": frozenset({"ticker"}),
    "get_orders": frozenset(),
    "get_order_history": frozenset({"limit", "ticker", "next_page_path"}),
    "get_transactions": frozenset({"limit", "next_page_path"}),
    "get_dividends": frozenset({"limit", "ticker", "next_page_path"}),
    "search_instruments": frozenset({"query", "limit"}),
    "get_exchanges": frozenset(),
    "get_pies": frozenset(),
    "get_pie": frozenset({"pie_id"}),
    "list_snapshots": frozenset({"start", "end", "cursor", "limit"}),
    "get_snapshot": frozenset({"snapshot_id", "offset", "limit"}),
}


class _StrictToolArguments:
    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        if ctx.method == "tools/call" and isinstance(ctx.params, Mapping):
            name = ctx.params.get("name")
            arguments = ctx.params.get("arguments") or {}
            if isinstance(name, str) and isinstance(arguments, Mapping):
                unexpected = set(arguments) - _TOOL_ARGUMENTS.get(name, frozenset())
                if unexpected:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text",
                                text="Invalid arguments: unexpected fields are not permitted",
                            )
                        ],
                        is_error=True,
                    )
        return await call_next(ctx)


def _default_client_factory() -> Trading212Client:
    return Trading212Client(Settings.from_env())


def create_server(client_factory: ClientFactory | None = None, *,
                  snapshot_store: SnapshotStore | None = None) -> MCPServer[Any]:
    """Create the MCP server, optionally using an injected client factory for tests."""
    factory = _default_client_factory if client_factory is None else client_factory
    catalog = MetadataCatalog()
    server: MCPServer[Any] = MCPServer(
        name="trading212-read-only",
        title="Trading 212 Read-Only",
        description="Read-only Trading 212 data, instrument catalogs, pies and NAS snapshots.",
        instructions=(
            "This server is strictly read-only. It cannot place, change, or cancel orders. "
            "Use exact Trading 212 tickers. Historical calls return one page; pass the returned "
            "next_page_path back to the same tool to continue."
            " Snapshot prices and quantities are decimal strings; preserve their currencies."
            " Snapshots are historical observations, not live data or investment returns."
        ),
        version=__version__,
        middleware=[_StrictToolArguments()],
    )

    async def invoke(operation: Callable[[Trading212Client], Awaitable[T]]) -> T:
        try:
            async with factory() as client:
                return await operation(client)
        except (ConfigError, Trading212Error, ValueError) as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError("Unexpected internal server error") from None

    @server.tool(
        title="Get account summary",
        description=(
            "Retrieve the Trading 212 account ID, primary currency, total value, cash breakdown, "
            "and investment profit/loss summary. Use for a complete account overview."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_account() -> dict[str, Any]:
        return await invoke(lambda client: client.get_account())

    @server.tool(
        title="Get cash balance",
        description=(
            "Retrieve only the primary currency and cash available to trade, reserved for orders, "
            "and held in pies. Use when the user asks about cash or buying power."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_cash() -> dict[str, Any]:
        return await invoke(lambda client: client.get_cash())

    @server.tool(
        title="Get portfolio",
        description=(
            "Retrieve every currently open Trading 212 position with instrument, quantity, price, "
            "cost, current value, and unrealized profit/loss data."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_portfolio() -> dict[str, Any]:
        positions = await invoke(lambda client: client.get_positions())
        return {"positions": positions}

    @server.tool(
        title="Get position by ticker",
        description=(
            "Retrieve the currently open position for one exact Trading 212 ticker. "
            "Use this instead of get_portfolio when the user identifies a single instrument."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_position(ticker: Ticker) -> dict[str, Any]:
        positions = await invoke(lambda client: client.get_positions(ticker=ticker))
        return {"positions": positions}

    @server.tool(
        title="Get pending orders",
        description=(
            "Retrieve all currently active pending orders and their execution status. "
            "This tool only reads orders and cannot change or cancel them."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_orders() -> dict[str, Any]:
        orders = await invoke(lambda client: client.get_orders())
        return {"orders": orders}

    @server.tool(
        title="Get order history",
        description=(
            "Retrieve one page of past orders and fills, optionally filtered by exact ticker. To "
            "continue, pass the returned next_page_path unchanged to this same tool."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_order_history(
        limit: Limit = 20,
        ticker: Ticker | None = None,
        next_page_path: NextPagePath | None = None,
    ) -> dict[str, Any]:
        return await invoke(
            lambda client: client.get_order_history(
                limit=limit,
                ticker=ticker,
                next_page_path=next_page_path,
            )
        )

    @server.tool(
        title="Get transactions",
        description=(
            "Retrieve one page of cash movements such as deposits, withdrawals, fees, "
            "and transfers. To continue, pass the returned next_page_path unchanged "
            "to this same tool."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_transactions(
        limit: Limit = 20,
        next_page_path: NextPagePath | None = None,
    ) -> dict[str, Any]:
        return await invoke(
            lambda client: client.get_transactions(
                limit=limit,
                next_page_path=next_page_path,
            )
        )

    @server.tool(
        title="Get paid dividends",
        description=(
            "Retrieve one page of paid dividends, optionally filtered by exact ticker. "
            "To continue, pass the returned next_page_path unchanged to this same tool."
        ),
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    async def get_dividends(
        limit: Limit = 20,
        ticker: Ticker | None = None,
        next_page_path: NextPagePath | None = None,
    ) -> dict[str, Any]:
        return await invoke(
            lambda client: client.get_dividends(
                limit=limit,
                ticker=ticker,
                next_page_path=next_page_path,
            )
        )

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS, structured_output=True)
    async def search_instruments(
        query: Annotated[str, Field(min_length=1, max_length=100)], limit: Limit = 20,
    ) -> dict[str, Any]:
        """Find instrument details by name, ticker or ISIN; exact matches rank first.

        Catalog data is cached for up to ten minutes. Narrow the query if truncated.
        """
        if not query.strip():
            raise ToolError("Instrument query must not be blank")
        items = await invoke(lambda client: catalog.read(client, "instruments"))
        return search_catalog(items, query, limit)

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS, structured_output=True)
    async def get_exchanges() -> dict[str, Any]:
        """Read exchanges and supplied trading schedules, cached up to ten minutes."""
        return {"exchanges": await invoke(lambda client: catalog.read(client, "exchanges"))}

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS, structured_output=True)
    async def get_pies() -> dict[str, Any]:
        """List existing pie summaries. Uses Trading 212's deprecated Pies API."""
        return {"pies": await invoke(lambda client: client.get_pies())}

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS, structured_output=True)
    async def get_pie(
        pie_id: Annotated[int, Field(strict=True, ge=1, lt=2**63)],
    ) -> dict[str, Any]:
        """Read one pie's holdings and settings. Uses the deprecated Pies API."""
        return await invoke(lambda client: client.get_pie(pie_id))

    async def read_snapshot(operation: Callable[[SnapshotStore], dict[str, Any]]) -> dict[str, Any]:
        try:
            store = snapshot_store
            if store is None:
                root = os.environ.get("T212_SNAPSHOT_DIR", "")
                if not root:
                    raise SnapshotError("Snapshot storage is not configured")
                environment = os.environ.get("T212_ENV", "demo").strip().lower()
                store = SnapshotStore(Path(root), environment)
            return await asyncio.to_thread(operation, store)
        except SnapshotError as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError("Unable to read snapshot data") from None

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS, structured_output=True)
    async def list_snapshots(
        start: str | None = None, end: str | None = None,
        cursor: str | None = None, limit: Limit = 20,
    ) -> dict[str, Any]:
        """List saved NAS captures newest first, with account totals and currencies.

        Optional inclusive start/end timestamps require a timezone. Pass next_cursor
        with the same filters to continue. Reads saved data without contacting Trading 212.
        """
        return await read_snapshot(lambda store: store.list(
            start=start, end=end, cursor=cursor, limit=limit))

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS, structured_output=True)
    async def get_snapshot(
        snapshot_id: Annotated[str, Field(pattern=r"^[0-9]{8}T[0-9]{12}Z$", max_length=22)],
        offset: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=200)] = 100,
    ) -> dict[str, Any]:
        """Read a saved capture's summary and a page of positions by its snapshot ID.

        Returns decimal strings for quantities and prices, with currency labels.
        Pass next_offset to continue. Cannot read arbitrary files or trigger a capture.
        """
        return await read_snapshot(lambda store: store.get(snapshot_id, offset=offset, limit=limit))

    @server.custom_route(  # type: ignore[untyped-decorator]
        "/health", methods=["GET"], include_in_schema=False
    )
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    return server


def _csv_setting(values: Mapping[str, str], name: str, default: str) -> list[str]:
    return [entry.strip() for entry in values.get(name, default).split(",") if entry.strip()]


def create_app(
    server: MCPServer[Any],
    *,
    environ: Mapping[str, str] | None = None,
) -> Any:
    """Create the ASGI app with an explicit Host/Origin allowlist."""
    values = os.environ if environ is None else environ
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_csv_setting(
            values,
            "MCP_ALLOWED_HOSTS",
            _DEFAULT_ALLOWED_HOSTS,
        ),
        allowed_origins=_csv_setting(
            values,
            "MCP_ALLOWED_ORIGINS",
            _DEFAULT_ALLOWED_ORIGINS,
        ),
    )
    return server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=transport_security,
    )


mcp = create_server()
app = create_app(mcp)


def main() -> None:
    """Run the ASGI application on the container's fixed port."""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
