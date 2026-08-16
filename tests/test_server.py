from __future__ import annotations

from types import TracebackType
from typing import Any, Self, cast

import httpx
import pytest
from mcp import Client
from mcp.server import MCPServer

from trading212_mcp.client import Trading212Client
from trading212_mcp.server import create_app, create_server

from .test_client import ACCOUNT, DIVIDEND, ORDER, POSITION, TRANSACTION


class FakeReadOnlyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get_account(self) -> dict[str, Any]:
        self.calls.append(("get_account", {}))
        return ACCOUNT

    async def get_cash(self) -> dict[str, Any]:
        self.calls.append(("get_cash", {}))
        return {
            "currency": "GBP",
            "availableToTrade": 2500.5,
            "reservedForOrders": 150.0,
            "inPies": 500.0,
        }

    async def get_positions(self, ticker: str | None = None) -> list[dict[str, Any]]:
        self.calls.append(("get_positions", {"ticker": ticker}))
        return [POSITION]

    async def get_orders(self) -> list[dict[str, Any]]:
        self.calls.append(("get_orders", {}))
        return [ORDER]

    async def get_order_history(
        self,
        *,
        limit: int = 20,
        ticker: str | None = None,
        next_page_path: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "limit": limit,
            "ticker": ticker,
            "next_page_path": next_page_path,
        }
        self.calls.append(("get_order_history", arguments))
        return {"items": [{"order": ORDER}], "next_page_path": None}

    async def get_transactions(
        self,
        *,
        limit: int = 20,
        next_page_path: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {"limit": limit, "next_page_path": next_page_path}
        self.calls.append(("get_transactions", arguments))
        return {"items": [TRANSACTION], "next_page_path": None}

    async def get_dividends(
        self,
        *,
        limit: int = 20,
        ticker: str | None = None,
        next_page_path: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, object] = {
            "limit": limit,
            "ticker": ticker,
            "next_page_path": next_page_path,
        }
        self.calls.append(("get_dividends", arguments))
        return {"items": [DIVIDEND], "next_page_path": None}


def server_and_fake() -> tuple[MCPServer[Any], FakeReadOnlyClient]:
    fake = FakeReadOnlyClient()
    return create_server(client_factory=lambda: cast(Trading212Client, fake)), fake


@pytest.mark.asyncio
async def test_server_exposes_exact_read_only_tool_metadata() -> None:
    server, _ = server_and_fake()

    async with Client(server) as client:
        response = await client.list_tools()

    tools = {tool.name: tool for tool in response.tools}
    assert set(tools) == {
        "get_account",
        "get_cash",
        "get_portfolio",
        "get_position",
        "get_orders",
        "get_order_history",
        "get_transactions",
        "get_dividends",
    }
    for tool in tools.values():
        assert tool.description
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.open_world_hint is False
        assert tool.input_schema["type"] == "object"

    transaction_properties = tools["get_transactions"].input_schema["properties"]
    assert transaction_properties["limit"]["minimum"] == 1
    assert transaction_properties["limit"]["maximum"] == 50
    assert transaction_properties["next_page_path"]["anyOf"][0]["maxLength"] == 2048
    position_properties = tools["get_position"].input_schema["properties"]
    assert position_properties["ticker"]["minLength"] == 1
    assert position_properties["ticker"]["maxLength"] == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected", "expected_call"),
    [
        ("get_account", {}, ACCOUNT, ("get_account", {})),
        (
            "get_cash",
            {},
            {
                "currency": "GBP",
                "availableToTrade": 2500.5,
                "reservedForOrders": 150.0,
                "inPies": 500.0,
            },
            ("get_cash", {}),
        ),
        (
            "get_portfolio",
            {},
            {"positions": [POSITION]},
            ("get_positions", {"ticker": None}),
        ),
        (
            "get_position",
            {"ticker": "AAPL_US_EQ"},
            {"positions": [POSITION]},
            ("get_positions", {"ticker": "AAPL_US_EQ"}),
        ),
        ("get_orders", {}, {"orders": [ORDER]}, ("get_orders", {})),
        (
            "get_order_history",
            {"limit": 2, "ticker": "AAPL_US_EQ"},
            {"items": [{"order": ORDER}], "next_page_path": None},
            (
                "get_order_history",
                {"limit": 2, "ticker": "AAPL_US_EQ", "next_page_path": None},
            ),
        ),
        (
            "get_transactions",
            {"limit": 2},
            {"items": [TRANSACTION], "next_page_path": None},
            ("get_transactions", {"limit": 2, "next_page_path": None}),
        ),
        (
            "get_dividends",
            {"limit": 2, "ticker": "AAPL_US_EQ"},
            {"items": [DIVIDEND], "next_page_path": None},
            (
                "get_dividends",
                {"limit": 2, "ticker": "AAPL_US_EQ", "next_page_path": None},
            ),
        ),
    ],
)
async def test_mcp_tool_calls_return_structured_data_and_forward_valid_arguments(
    tool_name: str,
    arguments: dict[str, object],
    expected: dict[str, Any],
    expected_call: tuple[str, dict[str, object]],
) -> None:
    server, fake = server_and_fake()

    async with Client(server) as client:
        result = await client.call_tool(tool_name, arguments)

    assert result.is_error is False
    assert result.structured_content == expected
    assert fake.calls == [expected_call]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("get_transactions", {"limit": 0}),
        ("get_transactions", {"limit": 51}),
        ("get_transactions", {"unexpected": True}),
        ("get_position", {"ticker": ""}),
        ("get_position", {}),
        ("get_order_history", {"next_page_path": "x" * 2049}),
    ],
)
async def test_invalid_mcp_arguments_are_rejected_before_client_calls(
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    server, fake = server_and_fake()

    async with Client(server) as client:
        result = await client.call_tool(tool_name, arguments)

    assert result.is_error is True
    assert fake.calls == []


@pytest.mark.asyncio
async def test_health_is_local_and_information_free() -> None:
    server, fake = server_and_fake()
    app = create_app(server, environ={})
    asgi_transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=asgi_transport,
        base_url="http://localhost",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert fake.calls == []
    rendered = response.text
    assert "T212" not in rendered
    assert "portfolio" not in rendered


@pytest.mark.asyncio
async def test_mcp_transport_rejects_unallowlisted_host() -> None:
    server, _ = server_and_fake()
    app = create_app(server, environ={})
    asgi_transport = httpx.ASGITransport(app=app)

    async with (
        httpx.AsyncClient(transport=asgi_transport, base_url="http://attacker.example") as client,
        app.router.lifespan_context(app),
    ):
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 421
