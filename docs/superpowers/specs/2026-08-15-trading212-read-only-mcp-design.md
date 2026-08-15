# Trading 212 Read-Only MCP Server Design

## Scope

Build a stateless Python service that exposes a small, read-only Trading 212
surface over MCP Streamable HTTP at `/mcp`, plus an information-free liveness
endpoint at `/health`. The service targets Docker Compose on a QNAP NAS.

## Researched Contracts

- Trading 212 uses HTTP Basic authentication with the API key as username and
  API secret as password.
- Official base URLs are `https://demo.trading212.com/api/v0` and
  `https://live.trading212.com/api/v0`.
- The supported account types are Invest and Stocks ISA.
- Historical orders, dividends, and transactions use cursor pagination and
  return `nextPagePath`; page size is at most 50.
- The official stable MCP Python SDK is `mcp==2.0.0`. It uses `MCPServer`, and
  Streamable HTTP is the production HTTP transport.
- The SDK's Streamable HTTP app serves `/mcp` and can register `/health` as a
  custom route. Stateless JSON responses are appropriate for this service.
- Remote ChatGPT connections require a reachable HTTPS Streamable HTTP endpoint
  or the official Secure MCP Tunnel. Public deployment also requires standard
  authentication/authorization; this first local version does not invent one.

## Architecture

`config.py` parses exactly `T212_API_KEY`, `T212_API_SECRET`, and `T212_ENV`,
validates complete credentials, and maps `demo` or `live` to a fixed base URL.

`client.py` owns one `httpx.AsyncClient` and exposes only named read methods. A
private request helper always sends GET and rejects paths outside a fixed
read-only allowlist. There is no generic public request method, no method
argument, and no order mutation method. Responses get basic shape validation.
HTTP errors are mapped to sanitized exceptions. A 429 includes only safe retry
metadata from response headers and is not retried automatically.

`server.py` creates an MCP 2.0 `MCPServer`, registers eight focused tools, marks
all tools read-only/non-destructive, and registers `/health`. Tools return
structured dictionaries and lists. `get_cash` projects the `cash` fields from
the official account-summary operation because the current operation catalog
does not expose a separate account-cash operation.

Historical tools fetch one bounded page. They accept the exact
`next_page_path` returned by a prior call; the client validates its path,
query, endpoint match, and origin before use. This avoids hidden loops, burst
traffic, and unbounded model context.

## Tool Surface

- `get_account`: full account summary.
- `get_cash`: cash and account currency from account summary.
- `get_portfolio`: all open positions.
- `get_position`: open position(s) for one exact Trading 212 ticker.
- `get_orders`: current pending orders.
- `get_order_history`: one page of historical orders, optionally by ticker.
- `get_transactions`: one page of cash transactions.
- `get_dividends`: one page of paid dividends, optionally by ticker.

## Trading 212 GET Allowlist

- `/api/v0/equity/account/summary`
- `/api/v0/equity/positions`
- `/api/v0/equity/orders`
- `/api/v0/equity/history/orders`
- `/api/v0/equity/history/transactions`
- `/api/v0/equity/history/dividends`

No POST, PUT, PATCH, or DELETE request can be constructed.

## Error And Security Design

Configuration and API exceptions never include credential values,
Authorization headers, response bodies, or complete upstream URLs with query
data. Logs remain at ASGI access/error level and do not log headers or tool
results. Pagination paths must be relative, stay on the expected endpoint, and
contain only documented query keys.

The server starts without calling Trading 212; `/health` therefore remains a
local liveness check. Credentials are loaded lazily when a tool first builds a
client, allowing health checks during deployment while still failing tool calls
cleanly when configuration is absent.

## Testing

Tests use `httpx.MockTransport`; no test contacts Trading 212. They cover
configuration, auth construction, environment selection, all client methods,
pagination, malformed payloads, HTTP/rate-limit errors, secret redaction, MCP
schemas and calls, invalid MCP arguments, health, and a source/tool audit for
write-capability names and HTTP mutation verbs.

## Deployment

Use a multi-stage `python:3.12-slim` image, install the wheel into a clean
runtime stage, run as an unprivileged user, expose port 8000, and use `/health`
for the Docker healthcheck. Compose sets `restart: unless-stopped`, reads values
from `.env`, and stores no state or credentials in the image.

