# Trading 212 Read-Only MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested, containerized, strictly read-only Trading 212 MCP server.

**Architecture:** A validated environment configuration feeds a named-method,
GET-only `httpx` client. An official MCP 2.0 `MCPServer` adapts those methods to
eight read-only tools over stateless JSON Streamable HTTP and adds `/health`.

**Tech Stack:** Python 3.12, MCP Python SDK 2.0, httpx, Pydantic, pytest, Ruff, mypy, Docker Compose.

## Global Constraints

- Only fixed Trading 212 retrieval endpoints may be called.
- No Trading 212 network request is made by tests.
- Credentials come only from `T212_API_KEY`, `T212_API_SECRET`, and `T212_ENV`.
- MCP is available at `/mcp`; health is `GET /health`.
- The service is stateless and has no UI, database, queue, or OpenAI API call.

---

### Task 1: Configuration And Packaging

**Files:** `pyproject.toml`, `src/trading212_mcp/config.py`,
`src/trading212_mcp/__init__.py`, `tests/test_config.py`

**Interfaces:** `Settings.from_env(environ: Mapping[str, str] | None) -> Settings`;
`Settings.base_url -> str`.

- [ ] Write tests for required credentials, secret-safe validation, normalized
  `demo`/`live`, rejected environments, and both fixed base URLs.
- [ ] Run `pytest tests/test_config.py -q` and confirm failures are caused by
  missing production code.
- [ ] Implement the minimal immutable Pydantic settings model and environment
  loader.
- [ ] Run the focused tests and confirm they pass.

### Task 2: GET-Only Trading 212 Client

**Files:** `src/trading212_mcp/client.py`, `tests/test_client.py`

**Interfaces:** `Trading212Client(settings, transport=None)` async context
manager; async methods `get_account`, `get_positions`, `get_orders`,
`get_order_history`, `get_transactions`, and `get_dividends` returning JSON-like
dictionaries/lists.

- [ ] Write mocked tests for Basic auth, timeout/configured URL, every named
  method, ticker filtering, bounded page size, next-page validation, malformed
  shapes, 401/403/408/429/5xx mapping, and credential redaction.
- [ ] Run `pytest tests/test_client.py -q` and confirm expected failures.
- [ ] Implement only the fixed GET allowlist, sanitized exception hierarchy,
  and one-page pagination.
- [ ] Run focused tests and the configuration tests.

### Task 3: MCP And Health Surface

**Files:** `src/trading212_mcp/server.py`, `tests/test_server.py`,
`tests/test_security.py`

**Interfaces:** `create_server(client_factory=None) -> MCPServer`, module-level
`mcp`, module-level ASGI `app`, and eight tool names from the design.

- [ ] Write in-memory MCP client tests that list tools, inspect schemas and
  annotations, call every tool against a fake client, reject invalid arguments,
  and test `/health` through an ASGI transport.
- [ ] Write security tests that reject write-like tool names, mutation strings,
  public generic request helpers, and order-write client methods.
- [ ] Run focused tests and confirm expected failures.
- [ ] Register the eight typed async tools, read-only annotations, sanitized
  tool errors, the custom health route, and stateless JSON HTTP app.
- [ ] Run all tests.

### Task 4: Container And Operator Documentation

**Files:** `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`,
`.gitignore`, `README.md`

**Interfaces:** container command serves `trading212_mcp.server:app` on port
8000; Compose service name `trading212-mcp`.

- [ ] Add packaging metadata, a multi-stage non-root image, Compose restart and
  health settings, secret-safe ignore files, and an environment template.
- [ ] Document architecture, endpoints, permissions, credentials, local and
  QNAP operation, inspection, security verification, and later remote access.
- [ ] Run Ruff, mypy, pytest, source security scans, package build, and Docker
  build when the engine is available.
- [ ] Start locally, call `/health`, list MCP tools with the official Python MCP
  client, and record exact outcomes.

