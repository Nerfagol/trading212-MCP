# Trading 212 Read-Only MCP Server

A minimal, stateless MCP server for reading a Trading 212 Invest or Stocks ISA
account from an MCP client. Run it locally with Docker, keep it LAN-only on a
QNAP NAS, or connect ChatGPT through OpenAI Secure MCP Tunnel.

## Read-only by design

This server implements exactly six allowlisted Trading 212 `GET` endpoints. It
has no buy, sell, create, place, cancel, modify, or update-order implementation,
and exposes no generic HTTP request method.

## Choose your deployment

| Route | Best for | Network exposure | Start here |
| --- | --- | --- | --- |
| Local Docker | Evaluation and development | Loopback only | `docker compose` |
| QNAP LAN-only | Trusted devices on your LAN | Fixed NAS LAN address | `deploy.sh mcp` |
| QNAP + Secure MCP Tunnel | ChatGPT and supported OpenAI products | Outbound HTTPS; no inbound public port | `deploy.sh tunnel` |

Start with Demo credentials. Trading 212 Demo and Live credentials are
environment-specific, so `T212_ENV` must match the account where the key was
created.

## Quick start: local Docker

Prerequisites: Git, Docker Engine, and Docker Compose v2.

```bash
git clone https://github.com/Nerfagol/trading212-MCP.git
cd trading212-MCP
cp .env.example .env
chmod 600 .env
# Edit .env. Start with a Demo key and T212_ENV=demo.
docker compose up -d --build
curl --fail --silent http://127.0.0.1:8000/health
```

The expected health response is `{"status":"ok"}`. The health check does not
load Trading 212 credentials or contact Trading 212. The local `.env` is ignored
by Git and excluded from the Docker build context.

The local endpoints are:

- MCP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`

To run from source instead, use Python 3.12 or later:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
set -a
. ./.env
set +a
python -m trading212_mcp.server
```

## Quick start: QNAP LAN-only

Prerequisites: Container Station, Docker Compose v2, SSH access with permission
to use Docker, and a fixed NAS LAN address.

Clone or securely transfer the repository into a persistent share such as:

```sh
cd /share/Container
git clone https://github.com/Nerfagol/trading212-MCP.git trading212-mcp
cd /share/Container/trading212-mcp
cp .env.example .env
chmod 600 .env
```

Edit `.env` with a protected editor. Set `MCP_BIND_ADDRESS` to the fixed NAS LAN
address, not `0.0.0.0`, and add that address with `:*` to
`MCP_ALLOWED_HOSTS`. Set `T212_ENV=demo` or `T212_ENV=live` to match the key.

Deploy only the MCP service and run the non-financial verifier:

```sh
./deploy/qnap/deploy.sh mcp
./deploy/qnap/verify.sh mcp
```

The deployment script affects only the named Compose project. The verifier
checks container health, LAN binding, and exact MCP tool discovery without
invoking any Trading 212 tool. See the [complete QNAP deployment guide](docs/qnap-deployment.md)
for configuration, updates, and rollback.

## Connect ChatGPT with Secure MCP Tunnel

Keep the MCP service bound to the NAS LAN address. OpenAI Secure MCP Tunnel runs
as a separate hardened container on the QNAP and makes an outbound HTTPS
connection to OpenAI. It does not require a public port, router forwarding,
public DNS, or a reverse proxy.

Create the tunnel and runtime key using the official
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
then prepare the protected QNAP files:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
# Populate protected files without putting values in shell history.
./deploy/qnap/tunnel/prepare-secrets.sh lock
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/verify.sh tunnel
```

The tunnel target is `http://<NAS_LAN_IP>:8000/mcp`. Port 8000 remains LAN-only,
the tunnel health/admin listener remains QNAP-loopback-only on port 18080, and
the tunnel Compose project publishes no ports. Follow the repository's
[Secure MCP Tunnel guide](docs/secure-mcp-tunnel.md) for protected-file formats,
verification, and the current ChatGPT Web connection flow.

## Verify the deployment

For local Docker:

```bash
docker compose ps
curl --fail --silent http://127.0.0.1:8000/health
```

For QNAP, use the scoped verifier appropriate to the deployed services:

```sh
./deploy/qnap/verify.sh mcp
./deploy/qnap/verify.sh tunnel
# Or, when both are deployed:
./deploy/qnap/verify.sh all
```

To inspect MCP discovery locally, start the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

Choose **Streamable HTTP**, connect to the private `/mcp` URL, and confirm the
eight tools listed below. Discovery alone does not call Trading 212. Run the
automated write-surface check with:

```bash
pytest tests/test_security.py -q
```

## MCP tools

| Tool | Purpose | Trading 212 request |
| --- | --- | --- |
| `get_account` | Account ID, currency, value, cash, and investment summary | `GET /api/v0/equity/account/summary` |
| `get_cash` | Available, reserved, and pie cash projected from account summary | `GET /api/v0/equity/account/summary` |
| `get_portfolio` | All open positions and current values and P/L | `GET /api/v0/equity/positions` |
| `get_position` | One open position by exact Trading 212 ticker | `GET /api/v0/equity/positions` |
| `get_orders` | Current pending orders, read-only | `GET /api/v0/equity/orders` |
| `get_order_history` | One page of historical orders and fills | `GET /api/v0/equity/history/orders` |
| `get_transactions` | One page of deposits, withdrawals, fees, and transfers | `GET /api/v0/equity/history/transactions` |
| `get_dividends` | One page of paid dividends | `GET /api/v0/equity/history/dividends` |

Historical tools accept `limit` from 1 to 50 and return at most one page per
call. Pass a returned `next_page_path` unchanged to the same tool for the next
page. The client rejects absolute URLs, other hosts, unknown query keys, and
paths for another endpoint.

Every tool advertises MCP `readOnlyHint: true`, `destructiveHint: false`, and
`openWorldHint: false`. The technical boundary is the fixed GET-only client,
not the annotations. See the [detailed MCP tool reference](docs/mcp-tools.md)
for arguments, response shapes, pagination, and error behavior.

## Trading 212 permissions

Generate credentials in the intended Demo or Live account under
**Settings > API (Beta)**. Trading 212 shows the secret once. See the official
[API key instructions](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key).

Enable only the read permissions needed by the tools you plan to use:

- account data for `get_account` and `get_cash`;
- portfolio for `get_portfolio` and `get_position`;
- history for orders, transactions, and dividends; and
- read-order access for `get_orders`, when available separately.

Do not enable trading or order-management permission when it is offered
separately. If Trading 212 bundles order reads with broader authority and you
prefer least privilege, omit that permission; `get_orders` may return 403 while
the server remains technically incapable of writing.

Required runtime variables are `T212_API_KEY` and `T212_API_SECRET`.
`T212_ENV` accepts `demo` or `live` and defaults to `demo`. Deployment variables
and safe defaults are documented in [`.env.example`](.env.example).

## Architecture

```text
ChatGPT -> OpenAI tunnel control plane -> tunnel-client on QNAP
                                               |
Trusted LAN MCP client ------------------------+
                                               |
                            LAN-only Streamable HTTP
                                               |
                            Trading 212 MCP server
                              /mcp      /health
                                               |
                           fixed GET-only API client
                                               |
                            Trading 212 Public API
```

The MCP service uses the official MCP Python SDK 2.0, stateless JSON Streamable
HTTP, and `httpx`. ChatGPT uses the optional outbound tunnel route; trusted LAN
clients can connect directly. `/health` is local to the service and contains no
configuration or account data.

## Security design

- Exactly six Trading 212 paths are allowlisted, and every request is `GET`.
- There is no generic request method and no buy, sell, order-placement,
  cancellation, modification, or update method in the MCP server or API client.
- Credentials are read from environment variables, kept in an in-memory Basic
  auth object, and excluded from responses, logs, and exception messages.
- Upstream response bodies and Authorization headers are never included in
  client-visible HTTP errors.
- A 429 is not retried automatically; safe numeric rate-limit timing may be
  returned without creating an infinite retry loop.
- Historical tools deliberately retrieve one validated page per call.
- MCP Host and Origin validation reduces DNS-rebinding risk.
- The containers run non-root with read-only filesystems, all capabilities
  dropped, `no-new-privileges`, small temporary filesystems, and no database.
- The QNAP MCP listener is bound to a fixed LAN address. The optional tunnel
  publishes no port and keeps its admin listener on `127.0.0.1`.

The security suite enumerates the MCP surface and inspects the API client AST
for mutating or generic HTTP calls. The QNAP verifier additionally rejects
write-like discovered tool names.

## Troubleshooting

| Symptom | Likely cause | Safe check |
| --- | --- | --- |
| Trading 212 returns 401 | Key ID/secret is invalid or belongs to the other environment | Confirm `T212_ENV` matches where the key was created; replace the protected files without printing them |
| A tool returns 403 | The key lacks that read permission | Review the key's account, portfolio, history, or read-order permissions |
| MCP returns 421 | The request Host is not allowlisted | Add the exact LAN host with `:*` to `MCP_ALLOWED_HOSTS`, then recreate only this service |
| MCP container is unhealthy | Configuration, bind address, or startup failure | Run `docker compose ps` and inspect redacted service logs; never print `.env` |
| Tunnel is not ready | Control-plane identity/key, outbound HTTPS, or private target reachability | Run `./deploy/qnap/verify.sh tunnel`; it discards raw doctor output |

For QNAP-specific Docker locations, rollback, and LAN-bound checks, use the
[QNAP deployment guide](docs/qnap-deployment.md). Do not paste `.env`, tunnel
credentials, raw doctor output, or account data into an issue.

## Detailed documentation

- [MCP tool reference](docs/mcp-tools.md)
- [QNAP deployment guide](docs/qnap-deployment.md)
- [Secure MCP Tunnel guide](docs/secure-mcp-tunnel.md)
- [QNAP operator command reference](deploy/qnap/README.md)

Development checks use mocked Trading 212 responses:

```bash
pytest
ruff check .
mypy
python -m build
```

No real credentials are required for the test suite.

## Related official resources

- [Trading 212 Public API documentation](https://docs.trading212.com/api)
- [Trading 212 agent-skills repository](https://github.com/trading212-labs/agent-skills)
- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Model Context Protocol transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Connect an MCP server to ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt)

The official Trading 212 agent-skills repository informed the API research for
this project. It includes trading actions. This project does not import or depend on agent-skills
and intentionally implements only allowlisted GET operations.

## Disclaimer

This independent project is not affiliated with or endorsed by Trading 212.
Trading 212 names are used only to describe interoperability. This software is
not financial advice. Review the source, permissions, and network boundary
before connecting an account.

## License

Licensed under the [MIT License](LICENSE).
