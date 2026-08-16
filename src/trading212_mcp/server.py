"""MCP Streamable HTTP server exposing only read-only Trading 212 tools."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Mapping
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
from trading212_mcp.client import Trading212Client, Trading212Error
from trading212_mcp.config import ConfigError, Settings

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


def create_server(client_factory: ClientFactory | None = None) -> MCPServer[Any]:
    """Create the MCP server, optionally using an injected client factory for tests."""
    factory = _default_client_factory if client_factory is None else client_factory
    server: MCPServer[Any] = MCPServer(
        name="trading212-read-only",
        title="Trading 212 Read-Only",
        description="Read-only account, portfolio, order, transaction, and dividend data.",
        instructions=(
            "This server is strictly read-only. It cannot place, change, or cancel orders. "
            "Use exact Trading 212 tickers. Historical calls return one page; pass the returned "
            "next_page_path back to the same tool to continue."
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
