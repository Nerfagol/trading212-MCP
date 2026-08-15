# QNAP Deployment Kit

This directory contains sanitized operations for the Trading 212 read-only MCP
server and optional OpenAI Secure MCP Tunnel. It contains no credentials,
tunnel identity, deployed NAS address, or financial data.

## Guides

- [MCP tool reference](../../docs/mcp-tools.md)
- [QNAP deployment guide](../../docs/qnap-deployment.md)
- [Secure MCP Tunnel](../../docs/secure-mcp-tunnel.md)

## First deployment

Configure the root `.env` as described in the QNAP guide. For the tunnel:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
# Populate the protected files with an editor or secure file transfer.
./deploy/qnap/tunnel/prepare-secrets.sh lock
```

Deploy and verify:

```sh
./deploy/qnap/deploy.sh all
./deploy/qnap/verify.sh all
```

Select only one service when required:

```sh
./deploy/qnap/deploy.sh mcp
./deploy/qnap/deploy.sh tunnel
./deploy/qnap/verify.sh mcp
./deploy/qnap/verify.sh tunnel
```

## Update

```sh
./deploy/qnap/update.sh all
./deploy/qnap/verify.sh all
```

`deploy.sh`, `update.sh`, and `verify.sh` operate only on these two named
projects. `prepare-secrets.sh` creates or locks local protected files without
reading or printing their values. None of the scripts prunes Docker resources,
changes QNAP configuration, invokes a Trading 212 tool, or opens a public port.

Never run deployment commands from a public checkout containing populated
`.env` or `secrets` files. Those files are ignored, but they remain sensitive
local state and should be backed up only through an encrypted process.
