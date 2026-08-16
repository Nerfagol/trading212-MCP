from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_NAME = "io.github.nerfagol/trading212-mcp"
IMAGE = "ghcr.io/nerfagol/trading212-mcp:0.1.0"
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


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_first_screen_states_product_and_security_model() -> None:
    readme = read("README.md")
    first_screen = "\n".join(readme.splitlines()[:75]).lower()

    for term in (
        "trading 212 mcp server",
        "model context protocol",
        "chatgpt",
        "self-hosted",
        "read-only by construction",
        "api keys stay on your server",
        "docker",
        "qnap",
        "openai secure mcp tunnel",
    ):
        assert term in first_screen
    assert "model never receives" in first_screen
    assert "buy, sell, place, create, cancel, update, or modify orders" in first_screen
    assert "```mermaid" in first_screen
    assert "outbound" in first_screen
    assert "allowlisted get" in first_screen


def test_readme_has_secure_versioned_ghcr_quick_start_and_discovery_terms() -> None:
    readme = read("README.md")

    assert f"docker pull {IMAGE}" in readme
    assert "docker run" in readme
    assert "-p 127.0.0.1:8000:8000" in readme
    assert "--read-only" in readme
    assert "--cap-drop ALL" in readme
    assert "--security-opt no-new-privileges" in readme
    assert "docker compose up -d --build" in readme
    for term in ("portfolio", "Stocks ISA", "Invest account", "Docker", "QNAP"):
        assert term in readme


def test_ci_workflow_has_least_privilege_and_all_release_gates() -> None:
    workflow = read(".github/workflows/ci.yml")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert re.search(r"permissions:\s+contents: read", workflow)
    for command in (
        "pip install -e '.[dev]'",
        "ruff check .",
        "mypy src tests",
        "pytest",
        "python -m build",
    ):
        assert command in workflow
    assert "docker/build-push-action" in workflow
    assert "push: false" in workflow
    assert "packages: write" not in workflow
    assert "ghcr.io" not in workflow
    assert_actions_are_pinned(workflow)


def test_release_workflow_publishes_only_on_published_release() -> None:
    workflow = read(".github/workflows/release-image.yml")

    assert "release:" in workflow
    assert "types: [published]" in workflow
    assert "pull_request:" not in workflow
    assert not re.search(r"^\s{2}push:", workflow, flags=re.MULTILINE)
    assert re.search(r"permissions:\s+contents: read\s+packages: write", workflow)
    assert "${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "ghcr.io/nerfagol/trading212-mcp" in workflow
    assert "type=semver,pattern={{version}}" in workflow
    assert "type=raw,value=latest" in workflow
    assert "push: true" in workflow
    assert "mcp-publisher publish" not in workflow
    assert_actions_are_pinned(workflow)


def assert_actions_are_pinned(workflow: str) -> None:
    action_lines = [line.strip() for line in workflow.splitlines() if "uses:" in line]
    assert action_lines
    for line in action_lines:
        assert re.search(r"@[0-9a-f]{40}(?:\s+#\s+v\d+)?$", line), line


def test_dockerfile_has_consistent_oci_and_registry_metadata() -> None:
    dockerfile = read("Dockerfile")

    expected_labels = {
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.source",
        "org.opencontainers.image.revision",
        "org.opencontainers.image.version",
        "org.opencontainers.image.licenses",
        "io.modelcontextprotocol.server.name",
    }
    for label in expected_labels:
        assert label in dockerfile
    assert f'io.modelcontextprotocol.server.name="{REGISTRY_NAME}"' in dockerfile
    assert "ARG VERSION=0.1.0" in dockerfile
    assert 'USER 10001:10001' in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_server_json_matches_current_registry_schema_and_release_image() -> None:
    metadata: dict[str, Any] = json.loads(read("server.json"))
    project = tomllib.loads(read("pyproject.toml"))["project"]

    assert metadata["$schema"] == (
        "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    )
    assert metadata["name"] == REGISTRY_NAME
    assert metadata["version"] == project["version"] == "0.1.0"
    assert metadata["repository"] == {
        "url": "https://github.com/Nerfagol/trading212-MCP",
        "source": "github",
        "id": "1335416380",
    }
    assert len(metadata["packages"]) == 1
    package = metadata["packages"][0]
    assert package["registryType"] == "oci"
    assert package["identifier"] == IMAGE
    assert package["runtimeHint"] == "docker"
    assert any(
        argument.get("name") == "--publish"
        and argument.get("value") == "127.0.0.1:8000:8000"
        for argument in package["runtimeArguments"]
    )
    assert package["transport"] == {
        "type": "streamable-http",
        "url": "http://127.0.0.1:8000/mcp",
    }
    environment = {item["name"]: item for item in package["environmentVariables"]}
    assert set(environment) >= {
        "T212_API_KEY",
        "T212_API_SECRET",
        "T212_ENV",
        "MCP_ALLOWED_HOSTS",
        "MCP_ALLOWED_ORIGINS",
    }
    for name in ("T212_API_KEY", "T212_API_SECRET"):
        assert environment[name]["isRequired"] is True
        assert environment[name]["isSecret"] is True


def test_release_version_and_python_package_metadata_are_consistent() -> None:
    project = tomllib.loads(read("pyproject.toml"))["project"]
    version = project["version"]

    assert project["license"] == "MIT"
    assert project["urls"]["Source"] == "https://github.com/Nerfagol/trading212-MCP"
    assert project["urls"]["Issues"].endswith("/issues")
    assert f'__version__ = "{version}"' in read("src/trading212_mcp/__init__.py")
    assert f'version="{version}"' in read("src/trading212_mcp/server.py")
    assert f"trading212-mcp/{version}" in read("src/trading212_mcp/client.py")
    assert f"ARG VERSION={version}" in read("Dockerfile")
    assert f'"version": "{version}"' in read("server.json")
    assert f"ghcr.io/nerfagol/trading212-mcp:{version}" in read("server.json")


def test_repository_policy_and_submission_material_are_present() -> None:
    security = read("SECURITY.md")
    contributing = read("CONTRIBUTING.md")
    pull_request = read(".github/pull_request_template.md")
    releasing = read("docs/releasing.md")
    submissions = read("docs/directory-submissions.md")

    assert "private vulnerability reporting" in security.lower()
    assert "docs/security.md" in security
    assert "real Trading 212 credentials" in contributing
    assert "read-only" in pull_request.lower()
    assert "mcp-publisher validate" in releasing
    assert "mcp-publisher publish" in releasing
    assert "must be run manually" in releasing
    assert "MCP Directory" in submissions
    assert "awesome-mcp-servers" in submissions
    assert "Strictly read-only Trading 212 MCP server" in submissions


def test_social_preview_is_correctly_sized_and_independent() -> None:
    preview = read("docs/assets/social-preview.svg")
    png = (ROOT / "docs/assets/social-preview.png").read_bytes()

    assert 'width="1280"' in preview
    assert 'height="640"' in preview
    assert "Trading 212 Read-Only MCP Server" in preview
    assert "Secure self-hosted portfolio access for ChatGPT &amp; MCP clients" in preview
    for label in ("READ-ONLY", "Docker", "QNAP", "Secure MCP Tunnel"):
        assert label in preview
    assert "not affiliated" in preview.lower()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_documented_tool_surface_is_exactly_eight_read_only_tools() -> None:
    tool_reference = read("docs/mcp-tools.md")
    headings = set(re.findall(r"^## `([^`]+)`", tool_reference, flags=re.MULTILINE))

    assert headings == EXPECTED_TOOLS
