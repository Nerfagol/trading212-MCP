from __future__ import annotations

import ast
import inspect

import pytest
from mcp import Client

import trading212_mcp.client as client_module
from trading212_mcp.client import Trading212Client

from .test_server import server_and_fake

WRITE_TOOL_TERMS = {
    "buy",
    "sell",
    "place",
    "create_order",
    "place_order",
    "cancel",
    "cancel_order",
    "modify",
    "modify_order",
    "update_order",
}


@pytest.mark.asyncio
async def test_mcp_exposes_no_write_or_trading_tool_names() -> None:
    server, _ = server_and_fake()

    async with Client(server) as client:
        names = {tool.name.lower() for tool in (await client.list_tools()).tools}

    violations = {name for name in names if any(term in name for term in WRITE_TOOL_TERMS)}
    assert violations == set()


def test_api_client_has_no_public_write_order_functionality() -> None:
    public_methods = {
        name
        for name, value in inspect.getmembers(Trading212Client, inspect.isfunction)
        if not name.startswith("_")
    }

    violations = {name for name in public_methods if any(term in name for term in WRITE_TOOL_TERMS)}
    assert violations == set()


def test_api_client_source_cannot_issue_mutating_or_generic_http_requests() -> None:
    tree = ast.parse(inspect.getsource(client_module))
    forbidden_http_calls = {"post", "put", "patch", "delete", "request", "send"}
    violations = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_http_calls
    }

    assert violations == set()
