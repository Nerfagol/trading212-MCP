# Development and Verification

## Repository layout

| Location | Responsibility |
| --- | --- |
| `src/trading212_mcp/` | Python package, fixed GET-only client and MCP tools |
| `tests/` | Mocked API, transport, storage and security regressions |
| `docs/` | User configuration, security and operator guides |
| `deploy/qnap/` | NAS scripts and QNAP-specific Compose overlays |
| `deploy/qnap/tunnel/` | Private tunnel image and its deployment files |
| Root Compose files | General local/container defaults and optional snapshots |

`compose-common.sh` shares Compose selection for mTLS and storage across the NAS
scripts. Keep persistent `snapshots` and `logs` in dedicated private host folders;
host-specific paths, credentials, certificates and deployment markers remain
ignored local state. Do not move live data as part of source-only reorganization.
Python wheels contain application code; source archives also contain sanitized
setup templates and exclude private operational state even outside Git.

Development and tests run locally without real Trading 212 credentials. All
network responses in the test suite use `httpx.MockTransport`.

## Requirements

- Python 3.12 or later
- Git
- Docker and Docker Compose v2 for container checks
- Node.js only when using the optional MCP Inspector

## Install

Create an isolated environment and install the pinned development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip install -e '.[dev]' --no-deps --no-build-isolation
python -m pip check
```

Do not put real credentials in test commands, fixtures, snapshots, or issue
reports.

## Tests and static checks

Run the complete local verification matrix:

```bash
pytest
ruff check .
mypy src tests
python -m build --no-isolation
```

Focused suites:

```bash
pytest tests/test_security.py -q
pytest tests/test_deployment_kit.py -q
```

The tests cover configuration, authentication construction, Demo/Live routing,
response parsing, pagination, errors, MCP calls, health, redaction, and the
absence of a write surface.

## Inspect MCP tools

Start the service with safe Demo credentials, then launch the official MCP
Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

Choose **Streamable HTTP**, enter `http://127.0.0.1:8000/mcp`, connect, and open
**Tools**. Confirm the exact fourteen names in the [MCP tool reference](mcp-tools.md)
and their read-only annotations. Discovery does not call Trading 212; a real API
request occurs only when a financial tool is invoked.

## Security review

The committed `requirements.txt`, `requirements-build.txt`, and
`requirements-dev.txt` lock every dependency and its artifact hashes. Docker
uses the runtime and build locks; CI installs the development lock. Regenerate
all three together on Python 3.12/Linux after changing `pyproject.toml`:

```bash
pip-compile --upgrade --generate-hashes --strip-extras --allow-unsafe --no-header --no-annotate --no-emit-index-url -o requirements.txt pyproject.toml
pip-compile --upgrade --generate-hashes --strip-extras --allow-unsafe --no-header --no-annotate --no-emit-index-url --build-deps-for wheel --only-build-deps -o requirements-build.txt pyproject.toml
pip-compile --upgrade --generate-hashes --strip-extras --allow-unsafe --no-header --no-annotate --no-emit-index-url -c requirements.txt -c requirements-build.txt --build-deps-for editable --extra dev -o requirements-dev.txt pyproject.toml
pip-audit --strict --disable-pip -r requirements.txt
pip-audit --strict --disable-pip -r requirements-build.txt
pip-audit --strict --disable-pip -r requirements-dev.txt
```

Use a fresh virtual environment when replacing an old installation so unused,
vulnerable packages are removed too. These locks are resolved on Python 3.12/Linux
and include verified wheel hashes for the Alpine container builds. Docker
requires binary runtime wheels and fails if a compatible hashed wheel is absent.
Regenerate and test for other Python versions or platforms.
Review and audit the regenerated locks before committing them. Do not suppress
an advisory solely because an upgrade is inconvenient.

CI also runs weekly and on manual request, and scans the freshly built runtime
amd64 and ARM64 images with Trivy. Every high and critical OS/Python finding
fails the image check,
including those without a published fix. There are no advisory ignore rules.
To repeat the image scan locally:

```bash
trivy image --scanners vuln --severity HIGH,CRITICAL --exit-code 1 trading212-mcp:local
```

Dependabot checks Python packages, GitHub Actions and the Docker base weekly.
Repository owners must also enable Dependabot alerts and security updates in
GitHub Settings; adding the configuration file alone does not enable alerts.

The primary automated check is:

```bash
pytest tests/test_security.py -q
```

Also inspect the client source for accidental mutating or generic HTTP calls:

```bash
rg -n -i '\.(post|put|patch|delete|request|send)\(|def (buy|sell|place|create_order|place_order|cancel|cancel_order|modify|modify_order|update_order)\b' src
```

Expected result: no match. Explanatory prose elsewhere in the repository may
contain words such as buy or cancel and is not executable functionality.

## Package build

Build the source distribution and wheel:

```bash
python -m build --no-isolation
```

Build the runtime container:

```bash
docker build --pull -t trading212-mcp:local .
```

Both stages use the official `python:3.12-alpine3.24` image. Alpine uses musl
instead of glibc, so runtime native dependencies must provide compatible binary
wheels. The runtime retains UID/GID 10001, the healthcheck, and the existing
container restrictions. No compiler or development tooling is installed there.
