"""Native MCP mutual TLS configuration and authenticated local health checks."""

from __future__ import annotations

import os
import ssl
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def server_options(values: Mapping[str, str]) -> dict[str, Any]:
    """Enable mandatory client verification when MCP_TLS_DIR is configured."""
    directory = values.get("MCP_TLS_DIR", "")
    if not directory:
        return {}
    root = Path(directory)
    if any(not (root / name).is_file() for name in (
        "server.crt", "server.key", "ca.crt", "health.crt", "health.key",
    )):
        raise ValueError("mTLS configuration is incomplete")
    return {
        "ssl_certfile": str(root / "server.crt"),
        "ssl_keyfile": str(root / "server.key"),
        "ssl_ca_certs": str(root / "ca.crt"),
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }


def client_context(directory: str) -> ssl.SSLContext:
    """Use the dedicated health identity with normal hostname verification."""
    root = Path(directory)
    context = ssl.create_default_context(cafile=str(root / "ca.crt"))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(root / "health.crt", root / "health.key")
    return context


def health() -> None:
    """Check only local health, never a financial tool or API."""
    directory = os.environ.get("MCP_TLS_DIR", "")
    scheme = "https" if directory else "http"
    context = client_context(directory) if directory else None
    with urllib.request.urlopen(
        f"{scheme}://127.0.0.1:8000/health", context=context, timeout=3,
    ) as response:
        if response.status != 200:
            raise ValueError("Health check failed")


if __name__ == "__main__":
    try:
        health()
    except Exception:
        raise SystemExit("MCP health check failed") from None
