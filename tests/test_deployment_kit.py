from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
QNAP = ROOT / "deploy" / "qnap"
TUNNEL = QNAP / "tunnel"

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

SCRIPTS = (
    QNAP / "deploy.sh",
    QNAP / "update.sh",
    QNAP / "verify.sh",
    TUNNEL / "prepare-secrets.sh",
)

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

PRIVATE_IPV4 = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)


def test_tunnel_compose_enforces_runtime_security_boundary() -> None:
    compose = (TUNNEL / "docker-compose.yml").read_text()

    for setting in (
        "restart: unless-stopped",
        "network_mode: host",
        "user: \"10001:10001\"",
        "read_only: true",
        "cap_drop:",
        "- ALL",
        "no-new-privileges:true",
        "HEALTH_LISTEN_ADDR=127.0.0.1:18080",
        "ALLOW_REMOTE_UI=false",
        "file:/run/secrets/control_plane_api_key",
    ):
        assert setting in compose

    assert re.search(r"^\s*ports:\s*$", compose, re.MULTILINE) is None
    assert PRIVATE_IPV4.search(compose) is None


def test_tunnel_image_is_pinned_by_digest() -> None:
    compose = (TUNNEL / "docker-compose.yml").read_text()
    digest = "sha256:a5b0b220577cdaeeb60a76d59700d03fb83ea8580c9c7871798ecadd09b4b71b"

    assert f"ghcr.io/openai/tunnel-client@{digest}" in compose


def test_tunnel_environment_example_contains_no_credentials() -> None:
    example = (TUNNEL / ".env.example").read_text()

    assert "CONTROL_PLANE_TUNNEL_ID=" in example
    assert "MCP_SERVER_URL=http://<NAS_LAN_IP>:8000/mcp" in example
    assert "OPENAI_API_KEY" not in example
    assert PRIVATE_IPV4.search(example) is None


def test_runtime_secret_paths_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text().splitlines()

    assert "**/.env" in ignore
    assert "**/.env.*" in ignore
    assert "!**/.env.example" in ignore
    assert "deploy/qnap/tunnel/secrets/" in ignore
    assert "deploy/qnap/tunnel/state/" in ignore
    assert "deploy/qnap/tunnel/*.log" in ignore


def test_docker_context_excludes_nested_credentials() -> None:
    ignore = (ROOT / ".dockerignore").read_text().splitlines()

    assert "**/.env" in ignore
    assert "**/.env.*" in ignore
    assert "**/secrets/" in ignore


def test_public_deployment_files_do_not_contain_live_nas_address() -> None:
    public_files = [
        path
        for path in (ROOT / "deploy").rglob("*")
        if path.is_file()
        and path.name != ".env"
        and path.suffix != ".pyc"
        and "secrets" not in path.parts
        and "__pycache__" not in path.parts
    ]

    for path in public_files:
        assert PRIVATE_IPV4.search(path.read_text()) is None


def _copy_deployment_tree(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(QNAP, project / "deploy" / "qnap")
    shutil.copy(ROOT / "docker-compose.yml", project / "docker-compose.yml")
    return project


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    docker = tmp_path / "docker"
    log = tmp_path / "docker.log"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
    docker.chmod(0o700)
    return docker, log


def test_shell_scripts_parse_and_contain_no_destructive_operations() -> None:
    forbidden = re.compile(
        r"set\s+-x|cat\s+.*\.env|cat\s+.*control_plane_api_key|"
        r"system\s+prune|volume\s+prune|network\s+prune|down\s+.*-v|rm\s+-rf",
        re.IGNORECASE,
    )

    for script in SCRIPTS:
        subprocess.run(["sh", "-n", str(script)], check=True)
        assert forbidden.search(script.read_text()) is None


def test_prepare_secrets_initializes_files_without_overwriting_them(tmp_path: Path) -> None:
    project = _copy_deployment_tree(tmp_path)
    tunnel = project / "deploy" / "qnap" / "tunnel"
    script = tunnel / "prepare-secrets.sh"

    subprocess.run(["sh", str(script), "init"], cwd=tunnel, check=True)

    environment = tunnel / ".env"
    api_key = tunnel / "secrets" / "control_plane_api_key"
    assert environment.stat().st_mode & 0o777 == 0o600
    assert api_key.stat().st_mode & 0o777 == 0o600

    environment.write_text("CONTROL_PLANE_TUNNEL_ID=sentinel\n")
    api_key.write_text("sentinel-key\n")
    subprocess.run(["sh", str(script), "init"], cwd=tunnel, check=True)
    assert environment.read_text() == "CONTROL_PLANE_TUNNEL_ID=sentinel\n"
    assert api_key.read_text() == "sentinel-key\n"


def test_prepare_secrets_refuses_to_lock_empty_files(tmp_path: Path) -> None:
    project = _copy_deployment_tree(tmp_path)
    tunnel = project / "deploy" / "qnap" / "tunnel"
    script = tunnel / "prepare-secrets.sh"
    subprocess.run(["sh", str(script), "init"], cwd=tunnel, check=True)

    result = subprocess.run(["sh", str(script), "lock"], cwd=tunnel, check=False)

    assert result.returncode != 0


def test_deploy_runs_only_quiet_scoped_compose_commands(tmp_path: Path) -> None:
    project = _copy_deployment_tree(tmp_path)
    tunnel = project / "deploy" / "qnap" / "tunnel"
    (project / ".env").write_text("configured\n")
    (tunnel / ".env").write_text("configured\n")
    (tunnel / "secrets").mkdir()
    (tunnel / "secrets" / "control_plane_api_key").write_text("configured\n")
    docker, log = _fake_docker(tmp_path)
    env = os.environ | {"DOCKER_BIN": str(docker), "DOCKER_LOG": str(log)}

    subprocess.run(
        ["sh", str(project / "deploy" / "qnap" / "deploy.sh"), "all"],
        cwd=project,
        env=env,
        check=True,
    )

    calls = log.read_text().splitlines()
    assert len(calls) == 4
    assert all("compose" in call for call in calls)
    assert "config --quiet" in calls[0]
    assert calls[1].endswith("up -d --build")
    assert "config --quiet" in calls[2]
    assert calls[3].endswith("up -d")


def test_update_uses_build_or_pull_without_cleanup(tmp_path: Path) -> None:
    project = _copy_deployment_tree(tmp_path)
    tunnel = project / "deploy" / "qnap" / "tunnel"
    (project / ".env").write_text("configured\n")
    (tunnel / ".env").write_text("configured\n")
    (tunnel / "secrets").mkdir()
    (tunnel / "secrets" / "control_plane_api_key").write_text("configured\n")
    docker, log = _fake_docker(tmp_path)
    env = os.environ | {"DOCKER_BIN": str(docker), "DOCKER_LOG": str(log)}

    subprocess.run(
        ["sh", str(project / "deploy" / "qnap" / "update.sh"), "all"],
        cwd=project,
        env=env,
        check=True,
    )

    calls = log.read_text().splitlines()
    assert len(calls) == 4
    assert calls[0].endswith("build --pull")
    assert calls[1].endswith("up -d")
    assert calls[2].endswith("pull")
    assert calls[3].endswith("up -d")


def _load_verify_mcp_module() -> ModuleType:
    path = QNAP / "verify_mcp.py"
    spec = importlib.util.spec_from_file_location("verify_mcp", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verifier_accepts_only_the_exact_read_only_tool_set() -> None:
    module = _load_verify_mcp_module()

    assert module.EXPECTED_TOOLS == EXPECTED_TOOLS
    assert module.validate_tool_names(EXPECTED_TOOLS) == []
    assert module.validate_tool_names(EXPECTED_TOOLS - {"get_cash"})
    assert module.validate_tool_names(EXPECTED_TOOLS | {"get_unknown"})


def test_verifier_rejects_every_write_like_tool_name() -> None:
    module = _load_verify_mcp_module()

    assert module.FORBIDDEN_TOOL_TERMS == FORBIDDEN_TOOL_TERMS
    for term in FORBIDDEN_TOOL_TERMS:
        assert module.validate_tool_names(EXPECTED_TOOLS | {f"prefix_{term}_suffix"})


def test_verifier_parses_json_and_sse_tool_responses() -> None:
    module = _load_verify_mcp_module()
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"tools": [{"name": name} for name in sorted(EXPECTED_TOOLS)]},
    }
    encoded = json.dumps(payload).encode()

    assert module.parse_tool_response(encoded, "application/json") == EXPECTED_TOOLS
    assert module.parse_tool_response(b"data: " + encoded + b"\n\n", "text/event-stream") == (
        EXPECTED_TOOLS
    )


def test_verify_cli_help_is_offline_and_successful() -> None:
    result = subprocess.run(
        [sys.executable, str(QNAP / "verify_mcp.py"), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "MCP_URL" in result.stdout


def test_nas_verifier_never_calls_financial_tools() -> None:
    script = (QNAP / "verify.sh").read_text()

    for tool in ("get_account", "get_cash", "get_portfolio"):
        assert tool not in script


def test_tool_documentation_covers_every_tool_and_endpoint() -> None:
    text = (ROOT / "docs" / "mcp-tools.md").read_text()

    for tool in EXPECTED_TOOLS:
        assert f"`{tool}`" in text
    for endpoint in {
        "/api/v0/equity/account/summary",
        "/api/v0/equity/positions",
        "/api/v0/equity/orders",
        "/api/v0/equity/history/orders",
        "/api/v0/equity/history/transactions",
        "/api/v0/equity/history/dividends",
    }:
        assert f"`GET {endpoint}`" in text


def test_qnap_documentation_covers_each_operational_script() -> None:
    guide = (ROOT / "docs" / "qnap-deployment.md").read_text()
    operator = (QNAP / "README.md").read_text()

    for script in ("deploy.sh", "update.sh", "verify.sh", "prepare-secrets.sh"):
        assert script in guide
        assert script in operator


def test_tunnel_documentation_uses_only_official_openai_links() -> None:
    text = (ROOT / "docs" / "secure-mcp-tunnel.md").read_text()
    links = re.findall(r"https://[^)\s]+", text)

    assert links
    assert all(link.startswith("https://developers.openai.com/") for link in links)


def test_operator_readme_links_all_detailed_guides() -> None:
    text = (QNAP / "README.md").read_text()

    for target in (
        "../../docs/mcp-tools.md",
        "../../docs/qnap-deployment.md",
        "../../docs/secure-mcp-tunnel.md",
    ):
        assert f"]({target})" in text


def test_repository_has_approved_mit_license() -> None:
    license_text = (ROOT / "LICENSE").read_text()

    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Nerfagol" in license_text
    assert "Permission is hereby granted, free of charge" in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text


def test_readme_starts_with_product_first_onboarding() -> None:
    readme = (ROOT / "README.md").read_text()
    headings = [
        "## 📊 What this gives you",
        "## 💬 Example questions",
        "## 🔒 Read-only by design",
        "## ✅ What to expect",
        "## 🚀 Choose your deployment",
        "## 🐳 Quick start: local Docker",
        "## 🗄️ Deploy on QNAP",
        "## 🔐 Connect ChatGPT securely",
        "## 🧰 MCP tools",
        "## 📚 Documentation",
    ]

    offsets = [readme.index(heading) for heading in headings]
    assert offsets == sorted(offsets)
    assert len(readme.splitlines()) <= 230


def test_readme_describes_supported_product_experience() -> None:
    readme = (ROOT / "README.md").read_text().lower()

    for expectation in (
        "structured account data",
        "not a browser dashboard",
        "demo",
        "live",
        "eight read-only tools",
        "sensitive financial data",
    ):
        assert expectation in readme


def test_readme_examples_map_only_to_supported_read_capabilities() -> None:
    readme = (ROOT / "README.md").read_text()
    examples = readme.split("## 💬 Example questions", 1)[1].split("\n## ", 1)[0].lower()

    for capability in (
        "account summary",
        "cash is available",
        "open positions",
        "pending orders",
        "transactions",
        "dividends",
    ):
        assert capability in examples
    for unsupported in ("forecast", "recommend", "should i buy", "tax report", "alert me"):
        assert unsupported not in examples


def test_root_readme_lists_exact_read_only_tool_surface() -> None:
    readme = (ROOT / "README.md").read_text()
    tools = readme.split("## 🧰 MCP tools", 1)[1].split("\n## ", 1)[0]
    documented = set(re.findall(r"`(get_[a-z_]+)`", tools))

    assert documented == EXPECTED_TOOLS


def test_readme_documents_all_deployment_entrypoints() -> None:
    readme = (ROOT / "README.md").read_text()

    for command in (
        "docker compose up -d --build",
        "./deploy/qnap/deploy.sh mcp",
        "./deploy/qnap/verify.sh mcp",
        "./deploy/qnap/tunnel/prepare-secrets.sh init",
        "./deploy/qnap/tunnel/prepare-secrets.sh lock",
        "./deploy/qnap/deploy.sh tunnel",
        "./deploy/qnap/verify.sh tunnel",
    ):
        assert command in readme


def test_readme_explains_official_agent_skills_relationship() -> None:
    readme = (ROOT / "README.md").read_text().lower()

    assert "https://github.com/trading212-labs/agent-skills" in readme
    assert "not affiliated with or endorsed by trading 212" in readme
    assert "does not import or depend on agent-skills" in readme
    assert "includes trading actions" in readme


def test_focused_documents_own_configuration_security_and_development() -> None:
    configuration = (ROOT / "docs" / "configuration.md").read_text()
    security = (ROOT / "docs" / "security.md").read_text()
    development = (ROOT / "docs" / "development.md").read_text()

    for variable in (
        "T212_API_KEY",
        "T212_API_SECRET",
        "T212_ENV",
        "MCP_BIND_ADDRESS",
        "MCP_ALLOWED_HOSTS",
        "MCP_ALLOWED_ORIGINS",
    ):
        assert f"`{variable}`" in configuration

    for statement in (
        "six allowlisted",
        "GET",
        "no generic",
        "OpenAI tunnel control plane",
        "tunnel-client on QNAP",
        "LAN-only Streamable HTTP",
    ):
        assert statement in security

    for command in ("pytest", "ruff check .", "mypy", "python -m build"):
        assert command in development


def test_all_root_readme_local_links_resolve() -> None:
    readme = (ROOT / "README.md").read_text()
    targets = re.findall(r"\]\(([^)]+)\)", readme)

    for target in targets:
        if "://" in target or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        assert (ROOT / path).exists(), target


def test_root_readme_links_the_complete_deployment_kit() -> None:
    readme = (ROOT / "README.md").read_text()

    for target in (
        "LICENSE",
        "docs/configuration.md",
        "docs/mcp-tools.md",
        "docs/security.md",
        "docs/development.md",
        "docs/qnap-deployment.md",
        "docs/secure-mcp-tunnel.md",
        "deploy/qnap/README.md",
    ):
        assert f"]({target})" in readme


def test_security_guide_includes_the_private_tunnel_route() -> None:
    security = (ROOT / "docs" / "security.md").read_text()

    for component in (
        "OpenAI tunnel control plane",
        "tunnel-client on QNAP",
        "LAN-only Streamable HTTP",
        "Trading 212 MCP server",
        "Trading 212 Public API",
    ):
        assert component in security
