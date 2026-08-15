# GitHub Sanitized Deployment Kit Design

## Goal

Add a public-safe, reproducible deployment kit for the existing Trading 212
read-only MCP server. The kit will document the MCP tools and the working QNAP
plus OpenAI Secure MCP Tunnel architecture without committing credentials,
account information, tunnel identifiers, fixed NAS addresses, or runtime data.

## Scope

The change is documentation and deployment automation only. It will not change
the Trading 212 client, MCP tool behavior, API permissions, or the server's
read-only security boundary.

The public repository will gain:

- detailed MCP tool documentation;
- a practical QNAP deployment guide;
- an OpenAI Secure MCP Tunnel guide based only on official OpenAI material;
- sanitized Compose configuration for the tunnel client;
- small scripts for preparation, deployment, updates, and verification; and
- ignore rules covering every generated credential and runtime file.

## Repository Layout

```text
deploy/
└── qnap/
    ├── README.md
    ├── deploy.sh
    ├── update.sh
    ├── verify.sh
    └── tunnel/
        ├── docker-compose.yml
        ├── .env.example
        └── prepare-secrets.sh

docs/
├── mcp-tools.md
├── qnap-deployment.md
├── secure-mcp-tunnel.md
└── superpowers/specs/...
```

The root `docker-compose.yml` remains the canonical Trading 212 MCP service.
The tunnel Compose file is separate because it has a distinct lifecycle and
uses credentials issued by OpenAI rather than Trading 212.

## Root README

The root README will remain the short entry point. Its existing tool table and
generic deployment overview will be retained, then linked to the detailed tool,
QNAP, and tunnel guides. The remote-connection section will describe the
implemented private-tunnel route instead of presenting it only as future work.

## MCP Tool Documentation

`docs/mcp-tools.md` will document all eight tools:

- `get_account`
- `get_cash`
- `get_portfolio`
- `get_position`
- `get_orders`
- `get_order_history`
- `get_transactions`
- `get_dividends`

For each tool, the guide will state its selection intent, arguments, structured
response shape, pagination behavior where applicable, Trading 212 endpoint,
and likely API permission. Examples will use synthetic tickers and values only.
The guide will explain the MCP read-only annotations while making clear that
the actual protection is the fixed GET-only client allowlist.

## QNAP Deployment Guide

`docs/qnap-deployment.md` will cover:

- prerequisites and supported Container Station Docker Compose operation;
- creating a persistent project directory under `/share/Container`;
- transferring the source without copying a local `.env` into Git history;
- creating a deployment `.env` with mode `600`;
- binding port 8000 to the NAS LAN address, not a wildcard address;
- setting `MCP_ALLOWED_HOSTS` for the chosen LAN address;
- starting, inspecting, updating, and restarting only this project;
- checking `/health` without calling Trading 212;
- optional read-only smoke checks without printing financial values;
- rollback using a previously tagged local image; and
- explicit prohibitions on router forwarding, public listeners, broad Docker
  cleanup commands, and modification of unrelated Container Station projects.

Examples will use placeholders such as `<NAS_LAN_IP>` and `<PROJECT_PATH>`.
They will not reproduce the operator's real credentials or tunnel identifier.

## Secure MCP Tunnel Guide

`docs/secure-mcp-tunnel.md` will describe the official OpenAI Secure MCP
Tunnel architecture and link to current official OpenAI documentation. It will
cover tunnel creation, runtime-key permissions, protected local storage,
authenticated `doctor`, persistent startup, health/readiness checks, ChatGPT
Web app creation, and tool review.

The guide will preserve these boundaries:

- the MCP server remains bound to its NAS LAN address;
- the tunnel client makes outbound control-plane connections only;
- no router forwarding, reverse proxy, public DNS, or public MCP listener is
  introduced;
- the tunnel health/admin listener binds to `127.0.0.1` only; and
- neither tunnel nor Trading 212 credentials are printed by the supplied
  operational commands.

## Tunnel Compose Template

`deploy/qnap/tunnel/docker-compose.yml` will use the official OpenAI tunnel
client image pinned to the verified release digest. Its controls will include:

- `restart: unless-stopped` and `init: true`;
- the image's unprivileged UID/GID;
- a read-only root filesystem and small `/tmp` tmpfs;
- all Linux capabilities dropped;
- `no-new-privileges:true`;
- no published ports;
- a loopback-only health/admin listener;
- remote UI disabled;
- the runtime API key mounted read-only as a file; and
- the tunnel identifier supplied by an ignored environment file.

The QNAP template will use host networking because the deployed MCP container
publishes only on the NAS LAN address and QNAP bridge networking could not
reach that host-bound listener. Host networking does not publish a tunnel port;
the admin listener remains explicitly bound to `127.0.0.1`.

No production IP address will be embedded. `MCP_SERVER_URL` will be supplied in
the ignored deployment `.env`, with a documented example value using
`<NAS_LAN_IP>`.

## Operational Scripts

### `prepare-secrets.sh`

Creates the ignored tunnel secret directory and expected empty configuration
paths with restrictive modes. It will never accept a secret on the command
line, since command arguments can be exposed through process listings and shell
history. The guide will direct the operator to use a local interactive editor
or another protected file-transfer method, then rerun the script's permission
validation.

### `deploy.sh`

Locates the QNAP Container Station Docker executable, validates required files
and permissions without reading their contents, validates Compose quietly, and
starts only the Trading 212 and tunnel projects requested by explicit flags.
It will not create shares, change QNAP settings, or prune Docker resources.

### `update.sh`

Builds or pulls current project images and recreates only the named project.
It preserves `.env` and secret files and will not use destructive cleanup
commands.

### `verify.sh`

Reports only non-sensitive booleans and names. It checks container state,
health/readiness endpoints, expected socket bindings, and MCP discovery. The
default path performs no Trading 212 API call. An explicit smoke-test option may
invoke only `get_account`, `get_cash`, and `get_portfolio`, while discarding
their returned financial data and reporting pass/fail only.

The security portion will reject MCP tools whose names contain `buy`, `sell`,
`place`, `create_order`, `place_order`, `cancel`, `cancel_order`, `modify`,
`modify_order`, or `update_order`.

## Secret Handling

The repository will include examples and directory structure only. Ignore rules
will cover:

- root and nested `.env` files except `.env.example`;
- `deploy/qnap/tunnel/secrets/`;
- tunnel client state, logs, and temporary output;
- local virtual environments and Python build/test artifacts.

Scripts will avoid `set -x`, credential-bearing command arguments, environment
dumps, rendered Compose output, and raw tunnel logs. Error messages will name a
missing file or failed check without displaying its contents.

## Verification

The completed change will be checked with:

1. shell syntax validation for every script;
2. Ruff, mypy, and the existing Python test suite;
3. Compose parsing with placeholder, non-secret values and quiet output;
4. a repository scan for credential-shaped values and accidentally tracked
   secret paths;
5. a scan for unsafe Docker operations and public port bindings;
6. confirmation that deployment scripts never print secret files; and
7. confirmation that documented/discovered tools are exactly the eight
   read-only tools.

Live NAS deployment will not be altered by this documentation change unless
the operator later runs the supplied scripts explicitly.
