# Trading 212 Read-Only MCP Server

A minimal, stateless MCP server for reading a Trading 212 Invest or Stocks ISA
account. It is deliberately unable to place, change, or cancel orders.

## Architecture

```text
ChatGPT or another MCP client
              |
       Streamable HTTP
              |
    /mcp  Trading 212 MCP server  /health
              |
     fixed GET-only API client
              |
       Trading 212 Public API
```

The service uses the official MCP Python SDK 2.0, stateless JSON Streamable
HTTP, and `httpx`. Credentials are read only when a tool is called; `/health`
does not contact Trading 212.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `get_account` | Account ID, currency, total value, cash, and investment summary |
| `get_cash` | Currency, available cash, reserved cash, and cash in pies |
| `get_portfolio` | All open positions and their current values and P/L |
| `get_position` | Open position for one exact Trading 212 ticker |
| `get_orders` | Current pending orders, read-only |
| `get_order_history` | One page of historical orders/fills, optionally by ticker |
| `get_transactions` | One page of deposits, withdrawals, fees, and transfers |
| `get_dividends` | One page of paid dividends, optionally by ticker |

Historical tools accept `limit` from 1 to 50. If a response contains
`next_page_path`, pass it unchanged to the same tool to fetch the next page.
The server validates the path and never follows another host or endpoint.

Every tool advertises MCP `readOnlyHint: true`, `destructiveHint: false`, and
`openWorldHint: false`. These annotations help clients, but the actual safety
boundary is the GET-only client implementation.

## Trading 212 endpoints

Only these requests are compiled into the client:

| Method | Endpoint | Tools |
| --- | --- | --- |
| `GET` | `/api/v0/equity/account/summary` | `get_account`, `get_cash` |
| `GET` | `/api/v0/equity/positions` | `get_portfolio`, `get_position` |
| `GET` | `/api/v0/equity/orders` | `get_orders` |
| `GET` | `/api/v0/equity/history/orders` | `get_order_history` |
| `GET` | `/api/v0/equity/history/transactions` | `get_transactions` |
| `GET` | `/api/v0/equity/history/dividends` | `get_dividends` |

There is no generic public HTTP method and no POST, PUT, PATCH, or DELETE call.
The API client rejects any path not in the table.

## Trading 212 credentials and permissions

Generate credentials in the Trading 212 web or mobile app:

1. Switch to the intended Demo or Live account.
2. Open **Settings > API (Beta)**.
3. Generate a key pair, select the minimum permissions, and preferably restrict
   the key to the NAS's outbound public IP or CIDR.
4. Store the API secret immediately; Trading 212 shows it once.

See Trading 212's current [API key instructions](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key).

The UI currently describes permissions such as account data, portfolio,
history, and orders. Enable account data, portfolio, and history for the
corresponding tools. `get_orders` may require the Orders permission. Do not
enable order-placement/trading permissions if the UI offers them separately.
If Orders is bundled with write authority and you prefer least privilege, omit
it; only `get_orders` should fail with 403 and the server still has no write
code.

Credentials are environment-specific. A Demo key does not work against Live
and vice versa.

## Environment variables

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `T212_API_KEY` | Yes | none | Trading 212 API key ID |
| `T212_API_SECRET` | Yes | none | Trading 212 API secret |
| `T212_ENV` | No | `demo` | `demo` or `live` |
| `MCP_BIND_ADDRESS` | Compose only | `127.0.0.1` | Host interface used for published port |
| `MCP_PORT` | Compose only | `8000` | Published host port |
| `MCP_ALLOWED_HOSTS` | No | local/container hosts | Comma-separated MCP Host-header allowlist |
| `MCP_ALLOWED_ORIGINS` | No | local HTTP origins | Comma-separated browser Origin allowlist |

Demo is the safe default. Selecting `live` only changes the fixed base URL; it
does not add any capability.

## Install and run locally

Python 3.12 or later is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'

export T212_API_KEY='your-key'
export T212_API_SECRET='your-secret'
export T212_ENV='demo'
python -m trading212_mcp.server
```

The endpoints are:

- MCP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`

```bash
curl --fail --silent http://127.0.0.1:8000/health
# {"status":"ok"}
```

## Tests and static checks

All Trading 212 responses are mocked with `httpx.MockTransport`.

```bash
pytest
ruff check .
mypy
python -m build
```

Security tests enumerate MCP tools, inspect public client methods, and parse the
client AST to reject mutating or generic HTTP calls.

```bash
pytest tests/test_security.py -q
rg -n -i 'buy|sell|place.order|cancel.order|modify.order|update.order|\.post\(|\.put\(|\.patch\(|\.delete\(' src
```

The word search will find explanatory text in tool descriptions or comments;
review each match. There must be no write tool and no mutating HTTP invocation.

## Inspect MCP tools

Start the server, then use the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

In the Inspector, choose **Streamable HTTP**, enter
`http://127.0.0.1:8000/mcp`, connect, and open **Tools**. Confirm the eight tool
names above, their schemas, and their read-only annotations. No real Trading 212
call occurs until you invoke a tool.

## Docker

Build directly:

```bash
docker build --pull -t trading212-mcp:local .
docker run --rm \
  --read-only --tmpfs /tmp:size=16m \
  --cap-drop ALL --security-opt no-new-privileges \
  -p 127.0.0.1:8000:8000 \
  -e T212_API_KEY \
  -e T212_API_SECRET \
  -e T212_ENV=demo \
  trading212-mcp:local
```

The image is based on `python:3.12-slim`, uses a multi-stage wheel build, and
runs as UID/GID 10001 rather than root.

## Docker Compose

```bash
cp .env.example .env
chmod 600 .env
# Edit .env; do not commit it.
docker compose config
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

Compose uses `restart: unless-stopped`, a healthcheck, a read-only filesystem,
a small `/tmp` tmpfs, no added capabilities, and no database or persistent
volume.

## Deployment kit

The repository includes a sanitized, reproducible QNAP deployment kit:

- [QNAP operator commands](deploy/qnap/README.md)
- [complete QNAP deployment guide](docs/qnap-deployment.md)
- [OpenAI Secure MCP Tunnel guide](docs/secure-mcp-tunnel.md)
- [detailed MCP tool reference](docs/mcp-tools.md)

The kit provides hardened tunnel Compose configuration and POSIX scripts for
secret-file preparation, deployment, updates, health/readiness checks, local
MCP discovery, and security verification. It includes no deployed NAS address,
tunnel identifier, API key, Trading 212 credential, or financial value.

For QNAP, place the project in a persistent path such as
`/share/Container/trading212-mcp`, set `MCP_BIND_ADDRESS` to the NAS's fixed LAN
address, set mode `600` on `.env`, and run:

```sh
./deploy/qnap/deploy.sh mcp
./deploy/qnap/verify.sh mcp
```

The verifier enumerates tool names without invoking them. Keep port 8000
LAN-only and never create a router port forward.

## Security design

- Only six fixed Trading 212 paths are allowlisted, and every request is GET.
- There are no buy, sell, placement, cancellation, modification, or update
  methods in either MCP or the API client.
- Credentials exist only in environment variables and an in-memory Basic auth
  object. They are not returned, logged, or interpolated into exceptions.
- HTTP errors never include upstream response bodies or Authorization headers.
- 429 responses are not retried automatically; only a numeric rate-limit reset
  timestamp is exposed.
- Historical calls fetch one page, avoiding infinite loops, request bursts, and
  unbounded model context.
- Pagination paths must be relative, match the same historical endpoint, and
  contain only documented query keys.
- MCP Host and Origin validation is enabled to reduce DNS-rebinding risk.
- `/health` returns only `{"status":"ok"}` and does not load credentials or call
  Trading 212.
- The runtime container is non-root, capability-free, stateless, and read-only.

The official Trading 212 skill repository includes trading actions and was used
only as research. None of its POST/DELETE behavior is included here. See the
[official skill](https://github.com/trading212-labs/agent-skills/tree/master/plugins/trading212-api/skills/trading212-api)
and the [current Trading 212 API reference](https://docs.trading212.com/api).

## Private remote connection with OpenAI Secure MCP Tunnel

The optional tunnel project connects the LAN-only `/mcp` endpoint to supported
OpenAI products using outbound HTTPS. It does not expose port 8000 or the tunnel
admin UI publicly. Runtime credentials remain in ignored, protected files and
are mounted read-only into the non-root tunnel container.

Follow the [Secure MCP Tunnel guide](docs/secure-mcp-tunnel.md), then run:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
# Populate protected files without placing values in shell history.
./deploy/qnap/tunnel/prepare-secrets.sh lock
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/verify.sh tunnel
```

Do not add router forwarding, a public reverse proxy, public DNS, or another
tunnel. See OpenAI's current
[Secure MCP Tunnel documentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
and [ChatGPT connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## Current-documentation decisions

- The current Trading 212 operation catalog exposes account summary, not a
  separate account-cash operation, although one quickstart still mentions
  `/account/cash`. `get_cash` therefore projects the documented account-summary
  response instead of calling an uncertain endpoint.
- Current historical endpoint pages state 6 requests per minute, while the
  official skill text still says 50 per minute. This server follows the current
  API pages, fetches one page per call, and does no automatic retry.
- MCP Python SDK 2.0 replaced older `FastMCP` examples with `MCPServer` and now
  supports the 2026-07-28 protocol. This project pins stable `mcp==2.0.0` and
  uses the current API.
- Streamable HTTP remains the recommended remote transport. SSE is not exposed.

Relevant protocol sources are the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
the [MCP transport specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports),
and the [Trading 212 pagination reference](https://docs.trading212.com/api/section/pagination).
