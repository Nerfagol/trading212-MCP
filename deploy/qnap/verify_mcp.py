#!/usr/bin/env python3
"""Enumerate the expected read-only MCP tools without invoking them."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

EXPECTED_TOOLS = {
    "get_account",
    "get_cash",
    "get_portfolio",
    "get_position",
    "get_orders",
    "get_order_history",
    "get_transactions",
    "get_dividends",
}

FORBIDDEN_TOOL_TERMS = {
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


def validate_tool_names(names: set[str]) -> list[str]:
    """Return safe validation errors for an MCP tool-name set."""
    errors: list[str] = []
    missing = EXPECTED_TOOLS - names
    extra = names - EXPECTED_TOOLS
    if missing:
        errors.append("expected read-only tools are missing")
    if extra:
        errors.append("unexpected tools are exposed")
    if any(term in name.lower() for name in names for term in FORBIDDEN_TOOL_TERMS):
        errors.append("a write-like tool name is exposed")
    return errors


def _tool_names(payload: object) -> set[str]:
    if not isinstance(payload, dict):
        raise ValueError("MCP response is not an object")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("MCP response has no result")
    tools = result.get("tools")
    if not isinstance(tools, list):
        raise ValueError("MCP response has no tool list")

    names: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ValueError("MCP tool metadata is malformed")
        names.add(tool["name"])
    return names


def parse_tool_response(body: bytes, content_type: str) -> set[str]:
    """Extract tool names from a JSON or server-sent-event MCP response."""
    if "text/event-stream" in content_type.lower():
        payloads: list[object] = []
        for line in body.decode("utf-8").splitlines():
            if line.startswith("data:"):
                payloads.append(json.loads(line.removeprefix("data:").strip()))
        if not payloads:
            raise ValueError("MCP event stream contained no data")
        return _tool_names(payloads[-1])

    return _tool_names(json.loads(body))


def _post_jsonrpc(
    url: str,
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
) -> tuple[bytes, str, str | None]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id is not None:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return (
                response.read(),
                response.headers.get("Content-Type", "application/json"),
                response.headers.get("Mcp-Session-Id", session_id),
            )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"MCP endpoint returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("MCP endpoint is unavailable") from None


def discover_tools(url: str) -> set[str]:
    """Initialize a Streamable HTTP MCP session and list tool names."""
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "trading212-deployment-verifier", "version": "1.0"},
        },
    }
    _, _, session_id = _post_jsonrpc(url, initialize)
    _post_jsonrpc(
        url,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session_id=session_id,
    )
    body, content_type, _ = _post_jsonrpc(
        url,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        session_id=session_id,
    )
    return parse_tool_response(body, content_type)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List and validate Trading 212 read-only MCP tool names."
    )
    parser.add_argument(
        "mcp_url",
        metavar="MCP_URL",
        nargs="?",
        default="http://127.0.0.1:8000/mcp",
    )
    args = parser.parse_args()

    try:
        names = discover_tools(args.mcp_url)
        errors = validate_tool_names(names)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"MCP discovery: FAIL ({exc})", file=sys.stderr)
        return 1

    if errors:
        print("MCP discovery: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    for name in sorted(names):
        print(name)
    print("MCP discovery: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
