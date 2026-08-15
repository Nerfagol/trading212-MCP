# QNAP Deployment Guide

This guide deploys the server on QNAP Container Station as two independent,
stateless Compose projects: the Trading 212 MCP service and the optional
outbound OpenAI tunnel client. It never configures a router, public listener,
reverse proxy, DNS record, or unrelated NAS service.

## Prerequisites

- A QNAP NAS with Container Station and Docker Compose v2.
- SSH access to an account allowed to run Container Station's Docker CLI.
- A fixed NAS LAN address.
- Trading 212 credentials generated for the intended Demo or Live environment.
- For remote ChatGPT use, an existing Secure MCP Tunnel and runtime key.

The scripts detect Docker at
`/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker`, then fall back to
`docker` on `PATH`. Set `DOCKER_BIN` to an executable path on QNAP models with a
different Container Station layout.

## Persistent project directory

Use a persistent share rather than a home or temporary directory:

```sh
mkdir -p /share/Container/trading212-mcp
```

Transfer this repository into that directory. Do not transfer `.venv`, `.deps`,
build output, a developer-machine `.env`, logs, or any secret directory. Never
commit the NAS `.env` back to GitHub.

All commands below start from:

```sh
cd /share/Container/trading212-mcp
```

## Configure Trading 212 MCP

Create the root environment from the example and restrict it before entering
values:

```sh
cp .env.example .env
chmod 600 .env
```

Set these values with a protected editor:

```dotenv
T212_API_KEY=<TRADING_212_KEY_ID>
T212_API_SECRET=<TRADING_212_SECRET>
T212_ENV=live
MCP_BIND_ADDRESS=<NAS_LAN_IP>
MCP_PORT=8000
MCP_ALLOWED_HOSTS=127.0.0.1:*,localhost:*,[::1]:*,trading212-mcp:*,<NAS_LAN_IP>:*
MCP_ALLOWED_ORIGINS=http://127.0.0.1:*,http://localhost:*,http://[::1]:*
```

Use `T212_ENV=demo` for a Demo key and `live` for a Live key. Credentials are
environment-specific. `MCP_BIND_ADDRESS` must be the fixed NAS LAN address, not
`0.0.0.0`. Browser origins are not needed for normal MCP clients.

## Configure the tunnel client

The tunnel is optional for LAN-only clients. To configure it without placing
credentials in arguments or shell history:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
```

Populate `deploy/qnap/tunnel/.env` and
`deploy/qnap/tunnel/secrets/control_plane_api_key` using a protected editor or
secure file transfer. Then lock ownership and modes:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh lock
```

See [Secure MCP Tunnel](secure-mcp-tunnel.md) for the required values and
ChatGPT steps. The script never prompts for or reads a secret. This avoids
depending on `stty`, which may be absent from QNAP's shell.

## Deploy

Choose one explicit target:

```sh
./deploy/qnap/deploy.sh mcp
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/deploy.sh all
```

`deploy.sh` validates Compose with `config --quiet`, builds only the MCP image,
and starts only the selected project. It does not stop, remove, or prune any
other container, volume, image, network, share, or QNAP configuration.

In Container Station, the expected containers are:

- `trading212-mcp`
- `openai-mcp-tunnel` when the tunnel is enabled

## Health and discovery

From a trusted LAN machine:

```sh
curl --fail --silent http://<NAS_LAN_IP>:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The health route does not load Trading 212 credentials or call Trading 212.

On the NAS, run:

```sh
./deploy/qnap/verify.sh mcp
./deploy/qnap/verify.sh tunnel
./deploy/qnap/verify.sh all
```

`verify.sh` checks container state, health/readiness, LAN-only binding, exact
MCP tool discovery, tunnel port exposure, and authenticated tunnel `doctor`.
Raw doctor output is discarded. The script lists tool names but never invokes
them and never retrieves account, cash, or portfolio values.

For an optional real read-only smoke test, use MCP Inspector or ChatGPT to call
only `get_account`, `get_cash`, and `get_portfolio`. Treat their outputs as
sensitive financial data and do not place them in logs, issue reports, or CI.

## Update

Before updating, optionally preserve the current MCP image locally:

```sh
docker image tag trading212-mcp:local trading212-mcp:rollback
```

Then update one target:

```sh
./deploy/qnap/update.sh mcp
./deploy/qnap/update.sh tunnel
./deploy/qnap/update.sh all
./deploy/qnap/verify.sh all
```

The MCP path builds with `--pull`; the tunnel path pulls its pinned digest.
Neither path runs `down`, removes data, or prunes Docker resources.

## Roll back the MCP image

If a new MCP build fails verification and the rollback tag exists:

```sh
docker image tag trading212-mcp:rollback trading212-mcp:local
docker compose --env-file .env -f docker-compose.yml up -d --no-build --force-recreate
./deploy/qnap/verify.sh mcp
```

Changing the pinned tunnel digest is a reviewed source change. Restore the
previous Compose file or repository release and run `update.sh tunnel`.

## LAN-only checks

Container Station should show host port 8000 bound to `<NAS_LAN_IP>`, not every
interface. The tunnel Compose file uses host networking only so it can reach
that LAN-bound host listener; it publishes no ports and binds its admin server
to `127.0.0.1:18080`.

Do not:

- create a router port forward for 8000 or 18080;
- bind either service to a public or wildcard address;
- create a public DNS record, reverse proxy, or third-party tunnel;
- expose the tunnel admin UI remotely;
- run broad `docker system prune`, volume prune, or network prune commands; or
- modify unrelated Container Station applications.
