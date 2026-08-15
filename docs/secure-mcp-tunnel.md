# OpenAI Secure MCP Tunnel

OpenAI Secure MCP Tunnel connects a private MCP server to supported OpenAI
products through an outbound HTTPS connection. It does not open an inbound NAS
port. The authoritative references are the official
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
and [ChatGPT connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## Architecture

```text
ChatGPT or another supported OpenAI product
                    |
          OpenAI tunnel control plane
                    |
          outbound HTTPS on port 443
                    |
      tunnel-client on the QNAP host
                    |
       private NAS LAN MCP endpoint
```

The MCP service stays bound to `<NAS_LAN_IP>:8000`. `tunnel-client` polls the
OpenAI control plane, forwards queued MCP JSON-RPC requests to that private URL,
and sends responses back through the outbound connection.

This route supports private developer-mode connections. It is not a public
plugin publication mechanism.

## Requirements

You need:

- a tunnel created in the intended OpenAI Platform organization;
- its `tunnel_id`;
- a separate runtime API key whose principal has Tunnels Read + Use;
- a ChatGPT workspace associated with the tunnel; and
- outbound QNAP access to `api.openai.com:443` and LAN access to the MCP URL.

Tunnel management and ChatGPT developer-mode permissions are separate. Do not
use an OpenAI admin key as the long-lived runtime key.

## Prepare protected files

From the repository root on QNAP:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh init
```

This creates:

- `deploy/qnap/tunnel/.env`, mode `600`; and
- `deploy/qnap/tunnel/secrets/control_plane_api_key`, mode `600` while editing.

Populate `.env` with the tunnel identity and private MCP URL:

```dotenv
CONTROL_PLANE_TUNNEL_ID=<TUNNEL_ID>
MCP_SERVER_URL=http://<NAS_LAN_IP>:8000/mcp
```

Place only the runtime API key in `secrets/control_plane_api_key`, followed by a
newline. Use a protected local editor or secure file transfer. Never pass either
value as a command argument, paste it into a chat, commit it, or include it in a
support log.

After writing both files:

```sh
./deploy/qnap/tunnel/prepare-secrets.sh lock
```

The lock action sets the runtime-key owner to the tunnel container's UID/GID
`10001:10001` and mode `400`. It validates only that files are non-empty and
does not display their contents.

## Compose security controls

The sanitized tunnel Compose project:

- pins the official image by digest;
- runs as UID/GID `10001:10001`;
- uses a read-only root filesystem and a 16 MiB `/tmp` tmpfs;
- drops all Linux capabilities and enables `no-new-privileges`;
- mounts the runtime key read-only as a file;
- publishes no container port;
- binds health and admin surfaces to `127.0.0.1:18080`;
- disables remote UI access; and
- restarts unless stopped.

QNAP host networking is intentional. A bridge-network container may not reach
an MCP port bound specifically to the NAS LAN address. Host networking provides
that private route without creating a published tunnel port. Loopback binding
keeps `/healthz`, `/readyz`, `/metrics`, and `/ui` off the LAN.

## Start and verify

Start only the tunnel project:

```sh
./deploy/qnap/deploy.sh tunnel
```

Verify its runtime without printing doctor details:

```sh
./deploy/qnap/verify.sh tunnel
```

The verifier checks:

- the container is running;
- `/healthz` returns success;
- `/readyz` returns success after control-plane polling begins;
- no ports are published;
- authenticated `tunnel-client doctor` exits successfully; and
- the private MCP target is reachable by the tunnel client.

The raw doctor stream is redirected away because diagnostic output can contain
deployment metadata. The official admin UI remains available only from the NAS
loopback interface and is not exposed to the LAN.

## Connect in ChatGPT Web

Keep `tunnel-client` healthy while creating or using the app:

1. Open ChatGPT Web settings.
2. Under **Security and login**, enable **Developer mode** if the workspace
   permits it.
3. Open the Plugins area and select the plus button to create an app.
4. Enter a name such as **Trading 212 Read-Only**.
5. Under **Connection**, select **Tunnel**.
6. Select the associated tunnel or enter the existing `tunnel_id`.
7. Create the connection and review discovered tools.
8. Confirm the exact eight names in [MCP Tool Reference](mcp-tools.md).
9. Confirm there is no buy, sell, place, create, cancel, modify, or update-order
   tool.
10. Start a new chat and enable the app from the tools menu.

ChatGPT-side discovery occurs only while the running client is ready. The local
verifier validates the private MCP surface and tunnel readiness but does not
simulate a ChatGPT product request.

## Network boundary

No inbound public access is required. Do not configure router forwarding,
public DNS, a public reverse proxy, a third-party tunnel, or a wildcard listener
for port 8000. Do not expose port 18080 or enable the remote tunnel UI.

The only intended paths are:

- QNAP to OpenAI over outbound HTTPS;
- QNAP tunnel client to the MCP server over the NAS LAN address; and
- trusted LAN clients to the explicitly LAN-bound health/MCP port when needed.
