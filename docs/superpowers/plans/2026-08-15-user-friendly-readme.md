# User-Friendly README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long operator-first README with a friendly product introduction and short onboarding paths while preserving detailed configuration, security, and development guidance in focused documents.

**Architecture:** Keep the application and deployment artifacts unchanged. The root README becomes a product overview and deployment router; three new documents own configuration, security, and contributor workflows. Documentation contract tests protect the exact read-only surface, realistic product expectations, deployment entry points, and local links.

**Tech Stack:** Markdown, pytest documentation checks, existing Docker Compose and POSIX deployment scripts.

## Global Constraints

- Do not modify the Trading 212 client, MCP server, Docker images, Compose behavior, scripts, tool schemas, or network exposure.
- Preserve exactly eight MCP tools and six allowlisted Trading 212 GET endpoints.
- Never add real credentials, tunnel identifiers, NAS addresses, financial values, screenshots, generated artwork, or unverifiable badges.
- Do not add Claude connection instructions until that route has been tested end to end.
- Keep the no-buy, no-sell, no-create, no-place, no-cancel, no-modify, and no-update-order guarantee prominent in the README.
- Keep Demo as the recommended first-run environment and describe Live as read-only real-account access.
- Use moderate emojis only on major product and onboarding headings; emojis must not replace meaningful labels.
- Keep minimum safe start and verification commands in the README; move detailed commands and controls into `docs/`.
- Use the external Git metadata directory `/tmp/trading212-publish-git.RgNsrd` because the workspace `.git` placeholder is read-only.

---

### Task 1: Add Product and Documentation Contracts

**Files:**
- Modify: `tests/test_deployment_kit.py`

**Interfaces:**
- Consumes: the approved design in `docs/superpowers/specs/2026-08-15-user-friendly-readme-design.md` and the current `ROOT`, `EXPECTED_TOOLS`, and deployment path constants in the test module.
- Produces: failing tests that define the product-first section order, supported example scope, detailed-document ownership, and resolvable README links.

- [ ] **Step 1: Replace the old deployment-first heading contract**

Replace `test_readme_starts_with_deployment_first_onboarding` with:

```python
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
    assert len(readme.splitlines()) <= 220
```

- [ ] **Step 2: Add product expectation and example-question contracts**

Add:

```python
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
```

- [ ] **Step 3: Add detailed-document ownership and link contracts**

Add:

```python
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
```

Extend `test_root_readme_links_the_complete_deployment_kit` so its target tuple
also requires `docs/configuration.md`, `docs/security.md`, and
`docs/development.md`.

- [ ] **Step 4: Move the architecture contract to the security guide**

Rename `test_root_architecture_includes_the_private_tunnel_route` to
`test_security_guide_includes_the_private_tunnel_route` and read from
`ROOT / "docs" / "security.md"`. Search the whole document for the existing
components rather than splitting a README section:

```python
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
```

- [ ] **Step 5: Run the focused tests and verify the red phase**

Run:

```bash
.venv/bin/pytest tests/test_deployment_kit.py -q
```

Expected: failures for the missing product-first headings and the three missing
focused documents. Existing deployment script, secret hygiene, tool reference,
official link, license, and QNAP guide checks remain green.

---

### Task 2: Create Focused Technical Guides

**Files:**
- Create: `docs/configuration.md`
- Create: `docs/security.md`
- Create: `docs/development.md`

**Interfaces:**
- Consumes: `.env.example`, `docker-compose.yml`, `src/trading212_mcp/config.py`, `src/trading212_mcp/client.py`, `Dockerfile`, `docs/qnap-deployment.md`, `docs/secure-mcp-tunnel.md`, and the existing verification commands.
- Produces: authoritative destinations for details removed from the root README.

- [ ] **Step 1: Create the configuration guide**

Create `docs/configuration.md` with these sections and content:

```text
# Configuration
## Trading 212 credentials
## Environment variables
## Demo and Live
## Local Docker
## Run from source
## Network binding and request validation
## Health endpoint
```

Include a complete table for `T212_API_KEY`, `T212_API_SECRET`, `T212_ENV`,
`MCP_BIND_ADDRESS`, `MCP_PORT`, `MCP_ALLOWED_HOSTS`, and
`MCP_ALLOWED_ORIGINS`. Preserve the local Docker and Python 3.12 setup commands
from the current README. Explain that `.env` is ignored, Demo and Live keys are
environment-specific, `MCP_BIND_ADDRESS` defaults to `127.0.0.1`, QNAP must use
its fixed LAN address rather than `0.0.0.0`, and `/health` does not load
credentials or call Trading 212.

- [ ] **Step 2: Create the security guide**

Create `docs/security.md` with these sections:

```text
# Security Design
## Read-only boundary
## Architecture
## Credentials and errors
## Pagination and rate limiting
## Container controls
## Network boundary
## Verify the write surface
```

Move the complete architecture diagram and security-control bullets from the
current README. Include the exact six GET endpoints, explain that the client has
no generic public request method, and distinguish MCP annotations from the
enforced client allowlist. Preserve credential redaction, safe error, no
automatic 429 retry, single-page pagination, Host/Origin validation, non-root
container, read-only filesystem, dropped capabilities, LAN-only MCP, and
loopback-only tunnel admin details. Link to `mcp-tools.md`,
`qnap-deployment.md`, and `secure-mcp-tunnel.md` instead of duplicating their
procedures.

- [ ] **Step 3: Create the development guide**

Create `docs/development.md` with these sections:

```text
# Development and Verification
## Requirements
## Install
## Tests and static checks
## Inspect MCP tools
## Security review
## Package build
```

Document Python 3.12, editable dev installation, mocked Trading 212 network
responses, `pytest`, `ruff check .`, `mypy`, `python -m build`, MCP Inspector,
and the source write-operation search. State that tests require no real
credentials and the Inspector performs no Trading 212 request until a tool is
invoked.

- [ ] **Step 4: Run the new detailed-document tests**

Run:

```bash
.venv/bin/pytest \
  tests/test_deployment_kit.py::test_focused_documents_own_configuration_security_and_development \
  tests/test_deployment_kit.py::test_security_guide_includes_the_private_tunnel_route \
  -q
```

Expected: both tests pass. Product-first README tests remain red.

---

### Task 3: Rewrite the README Around the Product Experience

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the three focused guides from Task 2 and existing QNAP, tunnel, and tool references.
- Produces: a concise product-first public landing document with safe deployment entry points.

- [ ] **Step 1: Replace the opening with product purpose and examples**

Use this exact top-level order:

```text
# Trading 212 Read-Only MCP Server
## 📊 What this gives you
## 💬 Example questions
## 🔒 Read-only by design
## ✅ What to expect
## 🚀 Choose your deployment
## 🐳 Quick start: local Docker
## 🗄️ Deploy on QNAP
## 🔐 Connect ChatGPT securely
## 🧰 MCP tools
## 📚 Documentation
## Official resources
## Disclaimer
## License
```

The first paragraph must say that the server lets ChatGPT or another MCP client
read a Trading 212 Invest or Stocks ISA account while the Trading 212
credentials remain in the self-hosted service.

- [ ] **Step 2: Describe supported outcomes without overclaiming**

Under `What this gives you`, cover account overview, available cash, open
positions, pending and historical orders, cash transactions, and paid
dividends. Under `Example questions`, include quoted prompts containing the six
phrases required by Task 1. Do not mention forecasting, recommendations, tax
reports, alerts, or any action that is not implemented.

Under `What to expect`, state that the product provides structured account data
through eight read-only tools, is not a browser dashboard, supports Demo and
Live, returns paginated history, has a minimal independent health endpoint, and
handles sensitive financial data that users should not paste into logs or
issues.

- [ ] **Step 3: Keep the compact read-only contract**

State prominently that only six allowlisted Trading 212 GET endpoints exist,
there is no generic HTTP method, and no buy, sell, create, place, cancel,
modify, or update-order code exists. Link to `docs/security.md` for the enforced
controls and verification details.

- [ ] **Step 4: Keep short, safe deployment entry points**

Retain the existing three-row deployment chooser. Keep the local Docker commands:

```bash
git clone https://github.com/Nerfagol/trading212-MCP.git
cd trading212-MCP
cp .env.example .env
chmod 600 .env
# Edit .env. Start with a Demo key and T212_ENV=demo.
docker compose up -d --build
curl --fail --silent http://127.0.0.1:8000/health
```

Keep only these QNAP entry points in the root README:

```sh
./deploy/qnap/deploy.sh mcp
./deploy/qnap/verify.sh mcp
```

Keep only these tunnel entry points:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
./deploy/qnap/tunnel/prepare-secrets.sh lock
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/verify.sh tunnel
```

Link the QNAP and tunnel sections to their detailed guides. Preserve the
LAN-only port 8000 and loopback-only port 18080 statements.

- [ ] **Step 5: Keep the exact tool summary and simplify the footer**

Retain the eight-row tool table, but use only `Tool` and `What it reads`
columns. Link to `docs/mcp-tools.md` for endpoints, arguments, pagination,
permissions, and response formats. Include one sentence directing readers to
the official MCP Inspector for local discovery and link to
`docs/development.md` for the command and verification procedure.

The Documentation section must link all seven local guides:

```text
docs/configuration.md
docs/mcp-tools.md
docs/security.md
docs/development.md
docs/qnap-deployment.md
docs/secure-mcp-tunnel.md
deploy/qnap/README.md
```

Keep official Trading 212 API, agent-skills, MCP SDK, OpenAI tunnel, and ChatGPT
connection links. Preserve the agent-skills independence statement, disclaimer,
and MIT license link. Target no more than 220 README lines.

- [ ] **Step 6: Run focused documentation tests**

Run:

```bash
.venv/bin/pytest tests/test_deployment_kit.py -q
```

Expected: all deployment-kit tests pass.

- [ ] **Step 7: Commit the tested documentation release**

```bash
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  add README.md docs/configuration.md docs/security.md docs/development.md \
  tests/test_deployment_kit.py \
  docs/superpowers/plans/2026-08-15-user-friendly-readme.md
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  commit -m "Make README product-focused"
```

---

### Task 4: Verify and Publish

**Files:**
- Modify: none unless verification reveals a documentation regression.

**Interfaces:**
- Consumes: the committed README, focused guides, and contract tests.
- Produces: a verified public `main` branch on `Nerfagol/trading212-MCP`.

- [ ] **Step 1: Run the full local verification matrix**

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy
PYTHONPATH=/home/sofozoboro/projects/trading212/.deps \
  .venv/bin/python -m build --no-isolation
find deploy/qnap -type f -name '*.sh' -exec sh -n {} \;
```

Expected: every command exits zero.

- [ ] **Step 2: Run publication security checks**

```bash
.venv/bin/pytest tests/test_security.py tests/test_deployment_kit.py -q
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  ls-files | rg '(^|/)\.env$|(^|/)secrets/'
rg -n -i '\.(post|put|patch|delete)\(|def (buy|sell|place|create_order|place_order|cancel|cancel_order|modify|modify_order|update_order)\b' src
```

Expected: tests pass and both searches return no matches. Confirm that the only
tracked environment files are `.env.example` and
`deploy/qnap/tunnel/.env.example`.

- [ ] **Step 3: Push the approved documentation commits**

```bash
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  push origin main
```

- [ ] **Step 4: Audit the public GitHub tree**

Use GitHub repository and tree APIs to verify that visibility remains `PUBLIC`,
the default branch remains `main`, the three new guides and updated README are
present, GitHub still recognizes the MIT license, and no `.env` or `secrets/`
path is tracked remotely.
