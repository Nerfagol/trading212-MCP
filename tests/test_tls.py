from __future__ import annotations

import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from trading212_mcp import tls


@pytest.fixture(scope="module")
def certificates(tmp_path_factory: pytest.TempPathFactory) -> Path:
    target = tmp_path_factory.mktemp("tls") / "certs"
    script = Path(__file__).resolve().parents[1] / "deploy/qnap/prepare-mtls.sh"
    subprocess.run(["sh", str(script), str(target), "127.0.0.1"], check=True)
    return target


@pytest.fixture(scope="module")
def listener(certificates: Path) -> Iterator[str]:
    from trading212_mcp.server import app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        app, log_level="critical",
        **tls.server_options({"MCP_TLS_DIR": str(certificates / "server")}),
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        yield f"https://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


def test_real_mtls_accepts_only_trusted_client(listener: str, certificates: Path) -> None:
    trusted = tls.client_context(str(certificates / "server"))
    with urllib.request.urlopen(listener + "/health", context=trusted, timeout=3) as response:
        assert response.read() == b'{"status":"ok"}'
    import runpy

    script = Path(__file__).resolve().parents[1] / "deploy/qnap/verify_mcp.py"
    verifier = runpy.run_path(str(script))
    names = verifier["discover_tools"](listener + "/mcp", context=trusted)
    assert names == verifier["EXPECTED_TOOLS"]
    no_certificate = ssl.create_default_context(cafile=str(certificates / "ca.crt"))
    server_identity = ssl.create_default_context(cafile=str(certificates / "ca.crt"))
    server_identity.load_cert_chain(
        certificates / "server/server.crt", certificates / "server/server.key",
    )
    for context in (no_certificate, server_identity, ssl.create_default_context()):
        with pytest.raises((urllib.error.URLError, ssl.SSLError, OSError)):
            urllib.request.urlopen(listener + "/health", context=context, timeout=3)
    with pytest.raises((urllib.error.URLError, OSError)):
        urllib.request.urlopen(listener.replace("https://", "http://") + "/health", timeout=3)


def test_wrong_client_ca_rejected(listener: str, certificates: Path, tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "deploy/qnap/prepare-mtls.sh"
    target = tmp_path / "other-ca"
    subprocess.run(["sh", str(script), str(target), "127.0.0.1"], check=True)
    context = ssl.create_default_context(cafile=str(certificates / "ca.crt"))
    context.load_cert_chain(target / "tunnel/tunnel.crt", target / "tunnel/tunnel.key")
    with pytest.raises((urllib.error.URLError, OSError)):
        urllib.request.urlopen(listener + "/health", context=context, timeout=3)


def test_tls_disabled_only_when_unconfigured() -> None:
    assert tls.server_options({}) == {}


def test_mtls_requires_client_certificate(certificates: Path) -> None:
    options = tls.server_options({"MCP_TLS_DIR": str(certificates / "server")})
    assert options["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert options["ssl_ca_certs"] == str(certificates / "server/ca.crt")


def test_missing_tls_files_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mTLS configuration is incomplete"):
        tls.server_options({"MCP_TLS_DIR": str(tmp_path)})


def test_certificate_setup_never_overwrites(certificates: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "deploy/qnap/prepare-mtls.sh"
    before = (certificates / "server/server.crt").read_bytes()
    result = subprocess.run(["sh", str(script), str(certificates), "127.0.0.1"])
    assert result.returncode != 0
    assert (certificates / "server/server.crt").read_bytes() == before


def test_leaf_roles_and_protected_keys(certificates: Path) -> None:
    for role in ("server", "tunnel"):
        assert (certificates / role / f"{role}.key").stat().st_mode & 0o777 == 0o400
    assert (certificates / "ca.key").stat().st_mode & 0o777 == 0o600
    result = subprocess.run([
        "openssl", "verify", "-purpose", "sslclient", "-CAfile",
        str(certificates / "server/ca.crt"), str(certificates / "server/server.crt"),
    ], capture_output=True)
    assert result.returncode != 0
