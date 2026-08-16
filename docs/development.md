# Development and Verification

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
python -m pip install -e '.[dev]'
```

Do not put real credentials in test commands, fixtures, snapshots, or issue
reports.

## Tests and static checks

Run the complete local verification matrix:

```bash
pytest
ruff check .
mypy src tests
python -m build
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
**Tools**. Confirm the exact eight names in the [MCP tool reference](mcp-tools.md)
and their read-only annotations. Discovery does not call Trading 212; a real API
request occurs only when a financial tool is invoked.

## Security review

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
python -m build
```

Build the runtime container:

```bash
docker build --pull -t trading212-mcp:local .
```

The multi-stage image installs the project wheel into `python:3.12-slim` and
runs as UID/GID 10001.
