# Configuration

The server reads its configuration from environment variables. It does not use
a database or configuration dashboard, and credentials must never be committed
to the repository.

## Trading 212 credentials

Create API credentials in the Trading 212 web or mobile app under
**Settings > API (Beta)** while viewing the intended Demo or Live account.
Trading 212 shows the API secret once, so store it in the protected deployment
environment immediately.

Use only the read permissions required by the tools you plan to enable:
account data, portfolio, history, and optional read-order access. Do not enable
trading or order-management permission when it is offered separately. See the
[MCP tool reference](mcp-tools.md) for the likely permission per tool and the
official [API key instructions](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key).

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `T212_API_KEY` | yes | none | Trading 212 API key identifier |
| `T212_API_SECRET` | yes | none | Trading 212 API secret |
| `T212_ENV` | no | `demo` | Trading 212 environment: `demo` or `live` |
| `MCP_BIND_ADDRESS` | Compose only | `127.0.0.1` | Host address where Docker publishes port 8000 |
| `MCP_PORT` | Compose only | `8000` | Published host port |
| `MCP_ALLOWED_HOSTS` | no | local and container hosts | Comma-separated MCP Host-header allowlist |
| `MCP_ALLOWED_ORIGINS` | no | local HTTP origins | Comma-separated browser Origin allowlist |

Start from the sanitized template:

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env` with a protected editor. The file is ignored by Git and excluded
from the Docker build context. Never print it in logs, issue reports, or support
requests.

## Demo and Live

Demo and Live credentials are environment-specific. A Demo key works only with
`T212_ENV=demo`; a Live key works only with `T212_ENV=live`.

Demo is the recommended first-run environment. Selecting Live changes only the
fixed Trading 212 API base URL. It does not add a write operation or change the
MCP tool surface.

## Local Docker

Docker Compose publishes the service on loopback by default:

```bash
docker compose config
docker compose up -d --build
docker compose ps
curl --fail --silent http://127.0.0.1:8000/health
```

Expected health response:

```json
{"status":"ok"}
```

Local endpoints:

- MCP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`

## Run from source

Python 3.12 or later is required:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
set -a
. ./.env
set +a
python -m trading212_mcp.server
```

The application listens on container/process port 8000. Use Docker's published
host address or a host firewall to define which machines can reach it.

## Network binding and request validation

`MCP_BIND_ADDRESS` controls the Docker host-side listener. Keep the local
default `127.0.0.1` unless a trusted LAN client must connect. On QNAP, use the
NAS's fixed LAN address rather than `0.0.0.0`, then add that address with `:*`
to `MCP_ALLOWED_HOSTS`.

`MCP_ALLOWED_HOSTS` validates the HTTP Host header. It is not a client-IP
firewall. Restrict client reachability with the bind address, NAS firewall, and
LAN segmentation as appropriate.

Normal non-browser MCP clients send no Origin header. Add an origin to
`MCP_ALLOWED_ORIGINS` only when a trusted browser-based client requires it.
The server enables Host and Origin validation to reduce DNS-rebinding risk.

For the complete NAS values and deployment procedure, see the
[QNAP deployment guide](qnap-deployment.md).

## Health endpoint

`GET /health` returns only `{"status":"ok"}`. It does not load Trading 212
credentials, contact Trading 212, disclose configuration, or return financial
data.
