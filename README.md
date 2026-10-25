# Trading 212 MCP Server: Read-Only

[![CI](https://github.com/Nerfagol/trading212-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/Nerfagol/trading212-MCP/actions/workflows/ci.yml) [![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](pyproject.toml) [![License: MIT](https://img.shields.io/badge/License-MIT-2F855A.svg)](LICENSE)

A self-hosted Trading 212 MCP server that gives ChatGPT and other Model Context Protocol
(MCP) clients structured access to an Invest account or Stocks ISA.
Trading 212 API credentials exist only on your server: the model never receives
the Trading 212 API key or secret.

**Read-only by construction · API keys stay on your server · No trading actions · Docker & QNAP ready**

The implementation cannot buy, sell, place, create, cancel, update, or modify orders.
It contains only explicitly allowlisted Trading 212 `GET` endpoints and exposes
no generic request or proxy method.

```mermaid
flowchart LR
    Remote["ChatGPT / remote MCP client<br/>No Trading 212 credentials"]
    OpenAI["OpenAI Secure MCP Tunnel"]

    subgraph Private["Private / trusted environment"]
        Local["Local MCP client"]
        Tunnel["tunnel-client"]
        Server["trading212-MCP<br/>Trading 212 credentials stay here"]

        Local -->|"loopback / trusted LAN"| Server
        Tunnel -->|"private /mcp"| Server
    end

    API["Trading 212 Public API<br/>allowlisted GET endpoints"]

    Remote -->|"remote MCP"| OpenAI
    OpenAI <-->|"outbound-initiated HTTPS"| Tunnel
    Server -->|"Basic auth · GET only"| API
```

The tunnel is optional. When used, its connection is initiated outbound from the
private environment; otherwise an MCP client can connect directly over loopback
or a trusted LAN. In both cases, credentials remain inside the self-hosted server.

## 📊 What this gives you

- A current account overview with currency, value, cost, and profit/loss data
- Available cash, cash reserved for orders, and cash held in pies
- Open positions, quantities, prices, current values, and unrealized P/L
- Pending orders plus paginated order history
- Deposits, withdrawals, fees, transfers, and paid dividends
- Instrument search, exchanges, pie reads, and optional four-hour CSV snapshots
- Structured responses that an MCP client can use directly in conversation

## 💬 Example questions

> Give me an account summary.

> How much cash is available to trade?

> Show my open positions and unrealized profit or loss.

> Do I have any pending orders?

> Show my recent transactions.

> What dividends have been paid?

## 🔒 Read-only by design

The client contains only allowlisted Trading 212 `GET` endpoints. It exposes
no generic request or proxy method and contains no code for buying, selling, creating,
placing, cancelling, modifying, or updating an order.

MCP annotations also mark every tool read-only, but the enforced boundary is
the GET-only client implementation. Review the complete [security design](docs/security.md)
and its automated write-surface checks.

## ✅ What to expect

- **Fourteen read-only tools** returning structured account data
- **Demo and Live support**, with Demo recommended for the first run
- **Paginated history**, returned one bounded page per tool call
- **No frontend**: this is not a browser dashboard; your MCP client is the interface
- **Independent health checking** that does not contact Trading 212
- **Private output**: account responses contain sensitive financial data and
  should not be copied into logs, issues, or public chats

## 🚀 Choose your deployment

| Route | Best for | Network exposure | Entry point |
| --- | --- | --- | --- |
| Local Docker | Evaluation and development | Loopback only | `docker compose` |
| QNAP LAN-only | Trusted devices on your LAN | Fixed NAS LAN address | `deploy.sh mcp` |
| QNAP + OpenAI Secure MCP Tunnel | ChatGPT and supported OpenAI products | Outbound HTTPS; no inbound public port | `deploy.sh tunnel` |

## 🐳 Quick start: build the current source

Prerequisites: Git, Docker Engine, Docker Compose v2, and Trading 212 Demo API
credentials.

```bash
git clone https://github.com/Nerfagol/trading212-MCP.git
cd trading212-MCP
cp .env.example .env
chmod 600 .env
# Edit .env. Start with a Demo key and T212_ENV=demo.
docker compose up -d --build
curl --fail --silent http://127.0.0.1:8000/health
```

- MCP: `http://127.0.0.1:8000/mcp`

See [Configuration](docs/configuration.md) for credentials, environments and network settings.

The Compose defaults publish only on loopback and retain the non-root user,
read-only filesystem, dropped capabilities, and `no-new-privileges` controls.
The published [0.2.0 release](https://github.com/Nerfagol/trading212-MCP/releases/tag/v0.2.0)
includes fourteen tools, mTLS and snapshots. Pull `ghcr.io/nerfagol/trading212-mcp:0.2.0`;
see the [published-image installation guide](docs/releasing.md#install-the-published-image).

## 🗄️ Deploy on QNAP

Place the project in a persistent Container Station directory, create the
protected root `.env`, and bind port 8000 to the NAS's fixed LAN address rather
than `0.0.0.0`. Then run:

```sh
./deploy/qnap/deploy.sh mcp
./deploy/qnap/verify.sh mcp
```

The verifier checks health, LAN binding, and the exact tool surface without
calling a financial tool. Follow the [QNAP deployment guide](docs/qnap-deployment.md)
for preparation, safe updates, rollback, and QNAP-specific Docker paths.

## 🔐 Connect ChatGPT securely

The optional OpenAI Secure MCP Tunnel runs separately on QNAP and reaches the
LAN-only MCP endpoint through an outbound HTTPS connection. Port 8000 remains
LAN-only, the tunnel admin listener remains loopback-only on port 18080, and no
router forwarding or public reverse proxy is required.

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
# Populate the protected files without putting values in shell history.
./deploy/qnap/tunnel/prepare-secrets.sh lock
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/verify.sh tunnel
```

Follow the [Secure MCP Tunnel guide](docs/secure-mcp-tunnel.md) for prerequisites,
protected-file formats, verification, and ChatGPT Web connection steps.

For protection against other devices and NAS apps, enable
[mutual TLS](docs/qnap-deployment.md#mutual-tls-on-the-nas) on the existing MCP
listener. Only clients holding a trusted certificate can connect. The tunnel
presents its own certificate; your ChatGPT app and tunnel ID stay the same.
No public port, public domain or separate OAuth server is required.

## 🗄️ Optional snapshot history and private logs

Snapshots require configured storage and the optional collector, saving account
totals and positions every four hours UTC without historical backfill.
MCP reads the history mount read-only; only the collector writes snapshots.

Follow the [snapshot setup](docs/snapshots.md) to prepare private `snapshots` and
`logs` folders and configure `deploy/qnap/storage.conf`. Rotating logs contain
status events only. Unconfigured storage returns a snapshot configuration error.

Use the supplied deploy/update scripts to preserve mTLS and storage overlays.
Keep persistent data separate from source; protect financial history even when
its parent is a NAS shared folder. See the [repository layout](docs/development.md#repository-layout).

## 🧰 MCP tools

| Tool | What it reads |
| --- | --- |
| `get_account` | Account currency, value, cash, cost, and profit/loss summary |
| `get_cash` | Available, reserved, and pie cash |
| `get_portfolio` | Every currently open position |
| `get_position` | One position by exact Trading 212 ticker |
| `get_orders` | Current pending orders and execution state |
| `get_order_history` | Historical orders and fills |
| `get_transactions` | Deposits, withdrawals, fees, and transfers |
| `get_dividends` | Paid dividends |
| `search_instruments` | Instruments matching ticker, name, or ISIN |
| `get_exchanges` | Exchange metadata and schedules |
| `get_pies` | Existing pies |
| `get_pie` | One pie's settings and instruments |
| `list_snapshots` | Saved capture times and account totals |
| `get_snapshot` | Saved summary and paginated positions |

See the [MCP tool reference](docs/mcp-tools.md) for arguments, Trading 212
endpoints, permissions, response formats, pagination, and safe errors. Use the
official MCP Inspector to verify local discovery by following the
[development guide](docs/development.md).

## 📚 Documentation

- [Configuration](docs/configuration.md): credentials, environments, local setup, and networking
- [CSV snapshots](docs/snapshots.md): four-hour NAS capture and MCP history access
- [MCP tool reference](docs/mcp-tools.md): tools, endpoints, arguments, and responses
- [Security design](docs/security.md): GET-only boundary, architecture, and runtime controls
- [Development and verification](docs/development.md): tests, linting, builds, and MCP Inspector
- [Release and Registry readiness](docs/releasing.md): versioning, GHCR, and metadata validation
- [Directory submission material](docs/directory-submissions.md): prepared summaries and current submission routes
- [QNAP deployment](docs/qnap-deployment.md): Container Station deployment and operations
- [Secure MCP Tunnel](docs/secure-mcp-tunnel.md): private ChatGPT connectivity
- [QNAP command reference](deploy/qnap/README.md): sanitized operational scripts

## Official resources

- [Trading 212 Public API](https://docs.trading212.com/api)
- [Trading 212 agent-skills repository](https://github.com/trading212-labs/agent-skills)
- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Official MCP Registry](https://modelcontextprotocol.io/registry/about)
- [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Connect an MCP server to ChatGPT](https://developers.openai.com/plugins/deploy/connect-chatgpt)

The official Trading 212 agent-skills repository informed the API research for
this project. It includes trading actions. This project does not import or depend on agent-skills
and intentionally implements only allowlisted GET operations.

## Disclaimer

This independent project is not affiliated with or endorsed by Trading 212.
Trading 212 names are used only to describe interoperability. This software is
not financial advice. Review its source, permissions, and network boundary
before connecting an account.

## License

Licensed under the [MIT License](LICENSE).
