# Deployment-First README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the engineer-oriented root README with deployment-first onboarding and add an MIT license so public users can legally deploy, modify, and redistribute the project.

**Architecture:** Keep the existing detailed tool, QNAP, and tunnel guides authoritative. The root README becomes a decision page with three short deployment paths, verification, troubleshooting, and links to deeper material. Documentation regression tests protect the route choices, exact tool surface, official attribution, independence statement, and license.

**Tech Stack:** Markdown, MIT License, pytest documentation checks, existing POSIX deployment scripts, Docker Compose.

## Global Constraints

- Do not change the Trading 212 client, MCP server, Docker runtime behavior, or tool schemas.
- Preserve exactly eight read-only MCP tools and the fixed GET-only API boundary.
- Never add real credentials, tunnel identifiers, NAS addresses, or financial data.
- Demo remains the documented first-run default; Live requires a matching Live key.
- The QNAP MCP listener remains LAN-only and the tunnel admin listener loopback-only.
- Do not recommend router forwarding, public reverse proxies, wildcard binding, or third-party tunnels.
- Link only official OpenAI documentation for Secure MCP Tunnel and ChatGPT behavior.
- Identify Trading 212 agent-skills as an official research reference, not a dependency or endorsement.
- Use MIT with `Copyright (c) 2026 Nerfagol`.
- Use the external Git metadata at `/tmp/trading212-publish-git.RgNsrd`; the workspace `.git` placeholder is read-only.

---

### Task 1: Add License and README Contract Tests

**Files:**
- Create: `LICENSE`
- Modify: `tests/test_deployment_kit.py`

**Interfaces:**
- Consumes: the approved repository identity `Nerfagol` and deployment paths already implemented under `deploy/qnap`.
- Produces: an MIT-licensed public source tree and regression expectations for the README rewrite.

- [ ] **Step 1: Add failing documentation and license tests**

Add tests with these behaviors:

```python
def test_repository_has_approved_mit_license() -> None:
    license_text = (ROOT / "LICENSE").read_text()
    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Nerfagol" in license_text
    assert "Permission is hereby granted, free of charge" in license_text
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in license_text


def test_readme_starts_with_deployment_first_onboarding() -> None:
    readme = (ROOT / "README.md").read_text()
    headings = [
        "## Choose your deployment",
        "## Quick start: local Docker",
        "## Quick start: QNAP LAN-only",
        "## Connect ChatGPT with Secure MCP Tunnel",
        "## Verify the deployment",
        "## MCP tools",
        "## Architecture",
        "## Troubleshooting",
    ]
    offsets = [readme.index(heading) for heading in headings]
    assert offsets == sorted(offsets)


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
```

Extend the existing root README link test to require `](LICENSE)`.

- [ ] **Step 2: Run focused tests and verify the red phase**

Run:

```bash
.venv/bin/pytest tests/test_deployment_kit.py -q
```

Expected: failures for missing `LICENSE`, missing deployment-first headings, and missing relationship wording. Existing deployment-kit tests remain green.

- [ ] **Step 3: Add the standard MIT license**

Create `LICENSE` with the standard MIT text and this exact first block:

```text
MIT License

Copyright (c) 2026 Nerfagol
```

Include the standard permission grant, copyright/permission notice condition,
and warranty/liability disclaimer without custom restrictions.

- [ ] **Step 4: Run the license test**

Run:

```bash
.venv/bin/pytest tests/test_deployment_kit.py::test_repository_has_approved_mit_license -q
```

Expected: one passing test. README contract tests remain red until Task 2.

- [ ] **Step 5: Leave the red README contracts uncommitted**

Do not commit Task 1 independently. The license test is green, but the README
contracts intentionally remain red until Task 2. Commit the license, tests,
and rewritten README together after the complete documentation contract passes.

---

### Task 2: Rewrite the Root README for Deployment-First Onboarding

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `docker-compose.yml`, `.env.example`, `deploy/qnap/*.sh`, `docs/mcp-tools.md`, `docs/qnap-deployment.md`, and `docs/secure-mcp-tunnel.md`.
- Produces: one first-screen deployment decision and verified command path for each supported environment.

- [ ] **Step 1: Replace the README introduction and deployment flow**

Use this exact top-level section order:

```text
# Trading 212 Read-Only MCP Server
## Read-only by design
## Choose your deployment
## Quick start: local Docker
## Quick start: QNAP LAN-only
## Connect ChatGPT with Secure MCP Tunnel
## Verify the deployment
## MCP tools
## Trading 212 permissions
## Architecture
## Security design
## Troubleshooting
## Detailed documentation
## Related official resources
## Disclaimer
## License
```

Keep the opening below 12 lines before `Choose your deployment`. State that the
server reads Invest or Stocks ISA data and has no buy, sell, create, place,
cancel, modify, or update-order implementation.

- [ ] **Step 2: Add the deployment chooser and local quick start**

The chooser table must contain:

| Route | Audience | Exposure | Entry point |
| --- | --- | --- | --- |
| Local Docker | evaluation/development | loopback-only | `docker compose` |
| QNAP LAN-only | trusted LAN clients | fixed NAS LAN address | `deploy.sh mcp` |
| QNAP + Secure MCP Tunnel | ChatGPT/supported OpenAI products | outbound HTTPS; no inbound public port | `deploy.sh tunnel` |

The local commands must be copy-pasteable:

```bash
git clone https://github.com/Nerfagol/trading212-MCP.git
cd trading212-MCP
cp .env.example .env
chmod 600 .env
# Edit .env. Start with a Demo key and T212_ENV=demo.
docker compose up -d --build
curl --fail --silent http://127.0.0.1:8000/health
```

State that `.env` is ignored, Demo and Live keys are environment-specific, and
`/health` does not contact Trading 212.

- [ ] **Step 3: Add QNAP and tunnel quick starts**

The QNAP path must instruct the reader to copy/clone into
`/share/Container/trading212-mcp`, set a fixed `MCP_BIND_ADDRESS`, update
`MCP_ALLOWED_HOSTS`, and run:

```bash
./deploy/qnap/deploy.sh mcp
./deploy/qnap/verify.sh mcp
```

The tunnel path must link the official Secure MCP Tunnel guide and show:

```bash
./deploy/qnap/tunnel/prepare-secrets.sh init
# Populate protected files without putting values in shell history.
./deploy/qnap/tunnel/prepare-secrets.sh lock
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/verify.sh tunnel
```

State that port 8000 stays LAN-only, port 18080 stays loopback-only, and no
router forwarding is used.

- [ ] **Step 4: Add verification, tools, permissions, and architecture**

Verification must cover `/health`, `verify.sh`, MCP Inspector, and
`pytest tests/test_security.py -q`. Retain the exact eight-tool table and link
to `docs/mcp-tools.md`. Recommend account data, portfolio, history, and optional
read-order permission only.

Retain the corrected architecture diagram showing:

```text
ChatGPT -> OpenAI tunnel control plane -> tunnel-client on QNAP
                                               |
Trusted LAN MCP client ------------------------+
                                               |
                            LAN-only Trading 212 MCP
                                               |
                                GET-only Trading 212 API
```

- [ ] **Step 5: Add concise security and troubleshooting sections**

Keep the GET-only allowlist, no generic HTTP method, protected credentials,
non-root/read-only containers, one-page pagination, safe error handling, Host
validation, and no public port claims.

Add a table for 401, 403, 421, unhealthy MCP, and tunnel-not-ready symptoms.
Commands may inspect state or health but must not print `.env`, raw doctor logs,
or account data.

- [ ] **Step 6: Add official resources, independence, disclaimer, and license**

Link:

- `https://docs.trading212.com/api`
- `https://github.com/trading212-labs/agent-skills`
- `https://developers.openai.com/api/docs/guides/secure-mcp-tunnels`
- `https://developers.openai.com/plugins/deploy/connect-chatgpt`

State verbatim that the project "does not import or depend on agent-skills" and
that the official agent-skills repository "includes trading actions" while
this project implements only allowlisted GET operations. State that the project
is not affiliated with or endorsed by Trading 212, is not financial advice, and
uses Trading 212 names only to describe interoperability. Link `[MIT](LICENSE)`.

- [ ] **Step 7: Run README regression tests**

Run:

```bash
.venv/bin/pytest tests/test_deployment_kit.py -q
```

Expected: all deployment-kit tests pass.

- [ ] **Step 8: Commit Tasks 1 and 2 together**

```bash
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  add LICENSE README.md tests/test_deployment_kit.py \
  docs/superpowers/plans/2026-08-15-deployment-first-readme.md
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  commit -m "Rewrite README for deployment-first onboarding"
```

---

### Task 3: Verify and Publish the Documentation Release

**Files:**
- Modify: none unless verification finds a documented regression.

**Interfaces:**
- Consumes: completed `README.md`, `LICENSE`, and documentation tests.
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

Expected: all commands exit zero.

- [ ] **Step 2: Run publication security checks**

```bash
.venv/bin/pytest tests/test_security.py tests/test_deployment_kit.py -q
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  ls-files | rg '(^|/)\.env$|(^|/)secrets/'
```

Expected: security tests pass and the tracked forbidden-path search returns no
matches. Confirm the only tracked environment files are `.env.example` and
`deploy/qnap/tunnel/.env.example`.

- [ ] **Step 3: Validate both Compose files quietly on QNAP**

Stream the public Compose files to QNAP's existing Compose parser using only
synthetic values and `config --quiet`. Do not read deployed `.env` files or
change running containers.

```bash
ssh qnap \
  "T212_API_KEY=example T212_API_SECRET=example T212_ENV=demo \
   MCP_BIND_ADDRESS=127.0.0.1 MCP_ALLOWED_HOSTS=localhost,127.0.0.1 \
   /share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker \
   compose -f - config --quiet" < docker-compose.yml

ssh qnap \
  "CONTROL_PLANE_TUNNEL_ID=example \
   MCP_SERVER_URL=http://192.0.2.10:8000/mcp \
   /share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker \
   compose -f - config --quiet" \
  < deploy/qnap/tunnel/docker-compose.yml
```

Expected: root and tunnel Compose validation both exit zero with no rendered
configuration output.

- [ ] **Step 4: Push the committed changes**

```bash
git --git-dir=/tmp/trading212-publish-git.RgNsrd \
  --work-tree=/home/sofozoboro/projects/trading212 \
  push origin main
```

- [ ] **Step 5: Verify the public repository**

Use GitHub's repository and tree APIs to confirm:

- visibility is `PUBLIC`;
- default branch is `main`;
- `LICENSE` and the new README are present; and
- no `.env` or `secrets/` path exists remotely.
