# GitHub Sanitized Deployment Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public-safe deployment kit that reproduces the Trading 212 MCP and official OpenAI Secure MCP Tunnel setup on QNAP without committing or printing secrets.

**Architecture:** Keep the root Compose service as the canonical Trading 212 MCP deployment and add a separate, hardened Compose project for the outbound tunnel client. Small POSIX shell scripts prepare, deploy, update, and verify the two services; detailed documents describe the eight MCP tools and operating procedures. Static pytest checks enforce the kit's security properties without needing credentials or NAS access.

**Tech Stack:** Docker Compose, QNAP Container Station Docker CLI, POSIX `sh`, Python 3.12/pytest for repository checks, MCP Streamable HTTP, official OpenAI `tunnel-client` image.

## Global Constraints

- Do not change `src/trading212_mcp/client.py`, MCP tool behavior, or Trading 212 permissions.
- Never commit, render, print, or accept credentials as command-line arguments.
- Keep the Trading 212 MCP listener bound to a selected NAS LAN address, never a public wildcard.
- Keep the tunnel health/admin listener on `127.0.0.1` and publish no tunnel ports.
- Use only the official OpenAI Secure MCP Tunnel and official OpenAI documentation.
- Pin the tunnel image to `ghcr.io/openai/tunnel-client@sha256:a5b0b220577cdaeeb60a76d59700d03fb83ea8580c9c7871798ecadd09b4b71b`.
- Preserve non-root execution, a read-only root filesystem, dropped capabilities, `no-new-privileges`, health checks, and `restart: unless-stopped`.
- Scripts may operate only on the Trading 212 MCP and tunnel Compose projects; never prune Docker or touch unrelated QNAP resources.
- Verification must not print account, cash, portfolio, Trading 212 credential, runtime API key, or tunnel ID values.
- Do not alter the running NAS deployment while building or testing this repository kit.
- This directory is not currently a Git worktree because `.git` is empty. Run commit steps only after the project is placed in a valid Git checkout; do not initialize or repair Git implicitly.

---

## File Map

**Create:**

- `deploy/qnap/README.md`: short operator entry point and command index.
- `deploy/qnap/deploy.sh`: validate and start one or both Compose projects.
- `deploy/qnap/update.sh`: update one or both projects without cleanup operations.
- `deploy/qnap/verify.sh`: run non-sensitive container, endpoint, binding, tool, and tunnel checks.
- `deploy/qnap/verify_mcp.py`: enumerate and validate local MCP tool metadata from inside the MCP container.
- `deploy/qnap/tunnel/docker-compose.yml`: hardened official tunnel-client deployment.
- `deploy/qnap/tunnel/.env.example`: non-secret tunnel settings template.
- `deploy/qnap/tunnel/prepare-secrets.sh`: create and lock protected credential files without reading values.
- `docs/mcp-tools.md`: exact tool selection, schema, endpoint, permission, and pagination reference.
- `docs/qnap-deployment.md`: complete QNAP deployment and lifecycle runbook.
- `docs/secure-mcp-tunnel.md`: official OpenAI tunnel and ChatGPT connection runbook.
- `tests/test_deployment_kit.py`: public-safety and deployment-template regression tests.

**Modify:**

- `.gitignore`: ignore nested deployment environments, tunnel secrets, state, and logs.
- `README.md`: link the detailed guides and describe the implemented private connection route.

---

### Task 1: Add Sanitized Tunnel Configuration and Security Tests

**Files:**
- Create: `tests/test_deployment_kit.py`
- Create: `deploy/qnap/tunnel/docker-compose.yml`
- Create: `deploy/qnap/tunnel/.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the private MCP URL supplied as `MCP_SERVER_URL` and a tunnel identifier supplied as `CONTROL_PLANE_TUNNEL_ID`.
- Produces: Compose service `tunnel-client`, secret path `deploy/qnap/tunnel/secrets/control_plane_api_key`, and loopback endpoints `http://127.0.0.1:18080/healthz` and `/readyz`.

- [ ] **Step 1: Write failing security tests**

Create tests that load files as text but never load `.env` or anything under a `secrets` directory:

```python
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TUNNEL = ROOT / "deploy" / "qnap" / "tunnel"
PRIVATE_IPV4 = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
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


def test_tunnel_compose_is_hardened_and_has_no_published_ports() -> None:
    compose = (TUNNEL / "docker-compose.yml").read_text()
    required = {
        "restart: unless-stopped",
        "read_only: true",
        "network_mode: host",
        "cap_drop:",
        "no-new-privileges:true",
        "HEALTH_LISTEN_ADDR=127.0.0.1:18080",
        "ALLOW_REMOTE_UI=false",
        "file:/run/secrets/control_plane_api_key",
    }
    assert required <= set(compose.splitlines()) | {
        line.strip() for line in compose.splitlines()
    }
    assert "ports:" not in compose
    assert PRIVATE_IPV4.search(compose) is None


def test_tunnel_image_is_pinned_by_digest() -> None:
    compose = (TUNNEL / "docker-compose.yml").read_text()
    digest = "sha256:a5b0b220577cdaeeb60a76d59700d03fb83ea8580c9c7871798ecadd09b4b71b"
    assert f"ghcr.io/openai/tunnel-client@{digest}" in compose


def test_runtime_secret_paths_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text().splitlines()
    assert "**/.env" in ignore
    assert "!**/.env.example" in ignore
    assert "deploy/qnap/tunnel/secrets/" in ignore
    assert "deploy/qnap/tunnel/state/" in ignore
    assert "deploy/qnap/tunnel/*.log" in ignore


def test_public_templates_contain_no_private_ipv4_address() -> None:
    public_files = [
        path
        for path in (ROOT / "deploy").rglob("*")
        if path.is_file() and path.name != ".env" and "secrets" not in path.parts
    ]
    for path in public_files:
        assert PRIVATE_IPV4.search(path.read_text()) is None
```

- [ ] **Step 2: Run the tests and confirm the assets are missing**

Run: `pytest tests/test_deployment_kit.py -q`

Expected: failures for missing `deploy/qnap/tunnel/docker-compose.yml` and missing ignore rules.

- [ ] **Step 3: Add sanitized environment and Compose templates**

The environment example must contain configuration names only:

```dotenv
CONTROL_PLANE_TUNNEL_ID=
MCP_SERVER_URL=http://<NAS_LAN_IP>:8000/mcp
```

The Compose service must use the pinned image, container name `openai-mcp-tunnel`, host networking, user `10001:10001`, and this command:

```yaml
command:
  - --control-plane.api-key=file:/run/secrets/control_plane_api_key
```

Map `CONTROL_PLANE_TUNNEL_ID` and `MCP_SERVER_URL` from `.env`, set JSON/info logging, bind health to `127.0.0.1:18080`, disable the remote UI, mount `./secrets/control_plane_api_key` read-only, use a 16 MiB `/tmp` tmpfs, drop all capabilities, and add a healthcheck against `/healthz` without publishing a port.

- [ ] **Step 4: Expand `.gitignore`**

Preserve current Python rules and replace the root-only environment rules with:

```gitignore
**/.env
**/.env.*
!**/.env.example
deploy/qnap/tunnel/secrets/
deploy/qnap/tunnel/state/
deploy/qnap/tunnel/*.log
```

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/test_deployment_kit.py -q`

Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit in a valid Git checkout**

```bash
git add .gitignore deploy/qnap/tunnel tests/test_deployment_kit.py
git commit -m "feat: add sanitized QNAP tunnel template"
```

---

### Task 2: Add Non-Destructive QNAP Lifecycle Scripts

**Files:**
- Create: `deploy/qnap/tunnel/prepare-secrets.sh`
- Create: `deploy/qnap/deploy.sh`
- Create: `deploy/qnap/update.sh`
- Modify: `tests/test_deployment_kit.py`

**Interfaces:**
- Consumes: action `mcp`, `tunnel`, or `all`; root `.env`; tunnel `.env`; tunnel runtime-key file.
- Produces: only Compose `up`, `build`, and `pull` operations scoped to the selected project.

- [ ] **Step 1: Add failing shell safety tests**

Add parameterized tests that run `sh -n` on all three scripts and statically reject unsafe behavior:

```python
SCRIPTS = [
    ROOT / "deploy/qnap/deploy.sh",
    ROOT / "deploy/qnap/update.sh",
    TUNNEL / "prepare-secrets.sh",
]


def test_shell_scripts_parse() -> None:
    for script in SCRIPTS:
        subprocess.run(["sh", "-n", str(script)], check=True)


def test_scripts_do_not_print_or_destroy_secret_state() -> None:
    forbidden = re.compile(
        r"set\s+-x|cat\s+.*\.env|cat\s+.*control_plane_api_key|"
        r"system\s+prune|volume\s+prune|down\s+.*-v|rm\s+-rf",
        re.IGNORECASE,
    )
    for script in SCRIPTS:
        assert forbidden.search(script.read_text()) is None
```

- [ ] **Step 2: Run focused tests and confirm missing-script failures**

Run: `pytest tests/test_deployment_kit.py -q`

Expected: failures because the scripts do not exist.

- [ ] **Step 3: Implement `prepare-secrets.sh`**

Use POSIX `sh`, `set -eu`, and `umask 077`. Support exactly two actions:

- `init`: create `secrets/`, copy `.env.example` to `.env` only when `.env` is absent, create an empty `secrets/control_plane_api_key` only when absent, and set both files to mode `600`.
- `lock`: require both files to be non-empty, set `.env` to `600`, change the key owner to `10001:10001`, and set the key to `400`.

Print only created paths, permission status, and instructions to edit the files securely. Do not read values, use `stty`, accept a secret argument, or overwrite a non-empty file.

- [ ] **Step 4: Implement `deploy.sh`**

Use POSIX `sh`. Resolve the repository root relative to the script. Detect Docker in this order:

1. executable from `DOCKER_BIN` when set;
2. `/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker`;
3. `docker` from `PATH`.

Accept exactly `mcp`, `tunnel`, or `all`. Before MCP deployment, require a non-empty root `.env`, run `docker compose --env-file .env config --quiet`, then `up -d --build`. Before tunnel deployment, require non-empty tunnel `.env` and runtime-key files, run Compose validation quietly, then `up -d`. Never render Compose configuration to stdout.

- [ ] **Step 5: Implement `update.sh`**

Use the same target and Docker detection rules. For `mcp`, run `build --pull` followed by `up -d`. For `tunnel`, run `pull` followed by `up -d`. For `all`, run both sequences. Do not run `down`, remove containers, remove images, or prune resources.

- [ ] **Step 6: Run shell and test verification**

Run:

```bash
sh -n deploy/qnap/deploy.sh
sh -n deploy/qnap/update.sh
sh -n deploy/qnap/tunnel/prepare-secrets.sh
pytest tests/test_deployment_kit.py -q
```

Expected: all commands pass without accessing credentials or Docker.

- [ ] **Step 7: Commit in a valid Git checkout**

```bash
git add deploy/qnap tests/test_deployment_kit.py
git commit -m "feat: add safe QNAP lifecycle scripts"
```

---

### Task 3: Add Non-Sensitive MCP and Tunnel Verification

**Files:**
- Create: `deploy/qnap/verify_mcp.py`
- Create: `deploy/qnap/verify.sh`
- Modify: `tests/test_deployment_kit.py`

**Interfaces:**
- Consumes: internal MCP URL `http://127.0.0.1:8000/mcp`, container names `trading212-mcp` and `openai-mcp-tunnel`, tunnel `/healthz` and `/readyz`.
- Produces: pass/fail status and the eight expected tool names; never prints tool results or credentials.

- [ ] **Step 1: Add failing verification tests**

Add tests that import `verify_mcp.py` through `importlib.util` and validate the exact allowlist and forbidden-name policy:

```python
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


def test_verifier_expects_exact_read_only_tool_set() -> None:
    module = load_verify_mcp_module()
    assert module.EXPECTED_TOOLS == EXPECTED_TOOLS
    assert module.validate_tool_names(EXPECTED_TOOLS) == []


def test_verifier_rejects_write_like_tool_names() -> None:
    module = load_verify_mcp_module()
    for term in FORBIDDEN_TOOL_TERMS:
        assert module.validate_tool_names(EXPECTED_TOOLS | {term})
```

Also include `verify.sh` in `SCRIPTS` and assert it contains no `get_account`, `get_cash`, or `get_portfolio` invocation. The repository verification script is intentionally network-only and must never retrieve financial data.

- [ ] **Step 2: Run focused tests and confirm failures**

Run: `pytest tests/test_deployment_kit.py -q`

Expected: failures because `verify_mcp.py` and `verify.sh` do not exist.

- [ ] **Step 3: Implement `verify_mcp.py`**

Use only the Python standard library. POST MCP JSON-RPC `initialize`, then `notifications/initialized`, then `tools/list` to the supplied URL with `Accept: application/json, text/event-stream`. Parse either a JSON response or `data:` events from an SSE response. Extract tool names only, compare them to `EXPECTED_TOOLS`, reject every forbidden substring case-insensitively, and print only sorted tool names plus `MCP discovery: PASS`.

Expose these stable interfaces for tests: `EXPECTED_TOOLS: set[str]`,
`FORBIDDEN_TOOL_TERMS: set[str]`, `validate_tool_names(names: set[str]) ->
list[str]`, `discover_tools(url: str) -> set[str]`, and `main() -> int`.

- [ ] **Step 4: Implement `verify.sh`**

Use Docker detection from Task 2 and accept optional target `mcp`, `tunnel`, or `all`, defaulting to `all`.

For MCP verification:

- require container `trading212-mcp` to be running and healthy;
- require `http://127.0.0.1:8000/health` to return HTTP 200 from inside the container;
- execute `python -` inside the container with `verify_mcp.py` supplied on stdin;
- inspect the published port and fail if its host IP is `0.0.0.0` or `::`.

For tunnel verification:

- require container `openai-mcp-tunnel` to be running and healthy;
- check `http://127.0.0.1:18080/healthz` and `/readyz` for HTTP 200;
- inspect the Compose configuration without rendering it and confirm there are no published ports;
- run authenticated `tunnel-client doctor` in a one-off container with `HEALTH_LISTEN_ADDR=127.0.0.1:18081`, redirecting its raw stdout and stderr to `/dev/null`, then print only the exit-status result.

State explicitly in script output that ChatGPT-side discovery is completed during app creation and is not simulated by this local check.

- [ ] **Step 5: Run focused tests**

Run:

```bash
python deploy/qnap/verify_mcp.py --help
sh -n deploy/qnap/verify.sh
pytest tests/test_deployment_kit.py -q
```

Expected: help exits zero, shell parsing passes, and all focused tests pass without network calls.

- [ ] **Step 6: Commit in a valid Git checkout**

```bash
git add deploy/qnap/verify.sh deploy/qnap/verify_mcp.py tests/test_deployment_kit.py
git commit -m "feat: add non-sensitive deployment verification"
```

---

### Task 4: Add Tool and Deployment Documentation

**Files:**
- Create: `docs/mcp-tools.md`
- Create: `docs/qnap-deployment.md`
- Create: `docs/secure-mcp-tunnel.md`
- Create: `deploy/qnap/README.md`
- Modify: `tests/test_deployment_kit.py`

**Interfaces:**
- Consumes: actual tool metadata in `src/trading212_mcp/server.py`, endpoints in `client.py`, and script commands from Tasks 2 and 3.
- Produces: public operator guidance with synthetic examples and official source links.

- [ ] **Step 1: Add failing documentation completeness tests**

Add tests requiring every expected tool name in `docs/mcp-tools.md`, all six fixed GET endpoints, the three lifecycle scripts in the QNAP guide, and official links in the tunnel guide:

```python
def test_tool_documentation_covers_exact_tool_set_and_endpoints() -> None:
    text = (ROOT / "docs/mcp-tools.md").read_text()
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


def test_tunnel_docs_use_only_official_openai_links() -> None:
    text = (ROOT / "docs/secure-mcp-tunnel.md").read_text()
    links = re.findall(r"https://[^)\s]+", text)
    assert links
    assert all(link.startswith("https://developers.openai.com/") for link in links)
```

- [ ] **Step 2: Run focused tests and confirm missing-document failures**

Run: `pytest tests/test_deployment_kit.py -q`

Expected: failures because the four documentation files do not exist.

- [ ] **Step 3: Write `docs/mcp-tools.md`**

Include:

- an exact eight-tool index;
- a section for each tool with when to use it, arguments, structured output keys, endpoint, and permission;
- `limit` range 1 through 50;
- exact `next_page_path` round-trip rules;
- synthetic examples using `AAPL_US_EQ` and explicitly fictional numeric values;
- a note that `get_cash` projects account-summary data rather than calling another endpoint;
- read-only annotations and the stronger GET-only path allowlist guarantee; and
- a forbidden-tool list matching the verifier.

- [ ] **Step 4: Write `docs/qnap-deployment.md`**

Document prerequisites, project transfer, fixed LAN address selection, root `.env` creation, mode `600`, `MCP_BIND_ADDRESS=<NAS_LAN_IP>`, allowed-host configuration, deploy/update/verify commands, Container Station health inspection, LAN health URL, rollback to a previously tagged image, and removal limited to the project containers. Explicitly prohibit public port forwarding and broad Docker prune commands.

- [ ] **Step 5: Write `docs/secure-mcp-tunnel.md`**

Use only these current official sources:

- `https://developers.openai.com/api/docs/guides/secure-mcp-tunnels`
- `https://developers.openai.com/plugins/deploy/connect-chatgpt`

Document the outbound-only architecture, tunnel/runtime-key prerequisites, `prepare-secrets.sh` workflow, protected manual file population, locking, deployment, `doctor`, health/readiness, LAN-only validation, and ChatGPT Web app creation. Explain that the tunnel is for private supported-product connections and not public plugin distribution.

- [ ] **Step 6: Write `deploy/qnap/README.md`**

Provide a compact operator sequence:

```bash
./tunnel/prepare-secrets.sh init
# Populate protected files without placing values in shell history.
./tunnel/prepare-secrets.sh lock
./deploy.sh all
./verify.sh all
```

Link the three detailed guides and warn that no script should be run from a public repository checkout containing real `.env` files.

- [ ] **Step 7: Run documentation tests**

Run: `pytest tests/test_deployment_kit.py -q`

Expected: all deployment-kit tests pass.

- [ ] **Step 8: Commit in a valid Git checkout**

```bash
git add docs deploy/qnap/README.md tests/test_deployment_kit.py
git commit -m "docs: add QNAP deployment and MCP tool guides"
```

---

### Task 5: Integrate the Root README and Run Full Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_deployment_kit.py`

**Interfaces:**
- Consumes: all deployment kit guides and scripts.
- Produces: one clear GitHub entry point and final regression coverage.

- [ ] **Step 1: Add a failing README link test**

```python
def test_root_readme_links_deployment_kit() -> None:
    readme = (ROOT / "README.md").read_text()
    for target in {
        "docs/mcp-tools.md",
        "docs/qnap-deployment.md",
        "docs/secure-mcp-tunnel.md",
        "deploy/qnap/README.md",
    }:
        assert f"]({target})" in readme
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `pytest tests/test_deployment_kit.py::test_root_readme_links_deployment_kit -q`

Expected: failure because the root README does not yet link all four files.

- [ ] **Step 3: Update the root README**

Add a `Deployment kit` section after Docker Compose linking the QNAP operator README, detailed QNAP guide, tunnel guide, and tool reference. Replace `Connecting remotely later` with `Private remote connection with OpenAI Secure MCP Tunnel`, summarize the outbound-only setup, retain the prohibition on forwarding port 8000, and link only official OpenAI documentation.

- [ ] **Step 4: Run all local quality checks**

Run:

```bash
pytest
ruff check .
mypy
python -m build
find deploy/qnap -type f -name '*.sh' -exec sh -n {} \;
```

Expected: all tests and checks pass.

- [ ] **Step 5: Validate Compose templates without displaying rendered secrets**

Use temporary fake values and quiet validation only:

```bash
docker compose -f docker-compose.yml --env-file .env.example config --quiet
CONTROL_PLANE_TUNNEL_ID=example \
MCP_SERVER_URL=http://192.0.2.10:8000/mcp \
docker compose -f deploy/qnap/tunnel/docker-compose.yml config --quiet
```

Expected: both commands exit zero and print no rendered configuration. If Docker is unavailable, record that the static tests and shell syntax checks passed and report Compose validation as unavailable.

- [ ] **Step 6: Run final repository security scans**

Run only against tracked/public candidates, explicitly excluding `.env`, `.git`, and secret paths:

```bash
rg -n '192\.168\.0\.157|sk-[A-Za-z0-9_-]{16,}|T212_API_(KEY|SECRET)=.+' \
  README.md docs deploy tests .env.example
rg -n -i 'docker (system|volume|network) prune|down .*-[^-]*v|set -x|cat .*\.env|cat .*control_plane_api_key' \
  deploy
pytest tests/test_security.py tests/test_deployment_kit.py -q
```

Expected: the first two searches return no credential, deployed address, destructive Docker, or secret-printing matches; both security test modules pass.

- [ ] **Step 7: Review final public tree**

Run: `find deploy docs -type f -not -path '*/secrets/*' -print | sort`

Expected: only specifications, plans, public documentation, example configuration, Compose, and operational source files are listed. No `.env`, secret, log, state, or account-data file appears.

- [ ] **Step 8: Commit in a valid Git checkout**

```bash
git add README.md tests/test_deployment_kit.py
git commit -m "docs: integrate sanitized deployment kit"
```
