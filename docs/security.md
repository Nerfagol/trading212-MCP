# Security Design

The project is read-only by implementation, not merely by tool descriptions or
model instructions. Its network surface and deployment templates are designed
for a small self-hosted service with optional private CSV storage.

## Read-only boundary

The Trading 212 client contains nine fixed paths and one numeric pie-ID path,
all requested with GET:

| Method | Endpoint |
| --- | --- |
| `GET` | `/api/v0/equity/account/summary` |
| `GET` | `/api/v0/equity/positions` |
| `GET` | `/api/v0/equity/orders` |
| `GET` | `/api/v0/equity/history/orders` |
| `GET` | `/api/v0/equity/history/transactions` |
| `GET` | `/api/v0/equity/history/dividends` |
| `GET` | `/api/v0/equity/metadata/instruments` |
| `GET` | `/api/v0/equity/metadata/exchanges` |
| `GET` | `/api/v0/equity/pies` |
| `GET` | `/api/v0/equity/pies/{id}` (positive integer below 2^63) |

There is no generic public HTTP request method. The client rejects any path not
in this allowlist and contains no POST, PUT, PATCH, or DELETE call. Neither the
client nor the MCP server implements buying, selling, placing, creating,
cancelling, modifying, or updating an order.

The fourteen MCP tools advertise `readOnlyHint: true`, `destructiveHint: false`,
and `openWorldHint: false`. Those annotations help an MCP host, but the enforced
boundary is the fixed GET-only API client. See the [MCP tool reference](mcp-tools.md)
for the exact tool surface.

## Architecture

```text
ChatGPT or another supported OpenAI product
                      |
           OpenAI tunnel control plane
                      |
       outbound HTTPS polling/responses
                      |
           tunnel-client on QNAP --------+
                                         |
Trusted LAN MCP client ------------------+
                                         |
                      LAN-only Streamable HTTP
                                         |
                  /mcp  Trading 212 MCP server  /health
                                         |
                        fixed GET-only API client
                                         |
                         Trading 212 Public API
```

The MCP server uses stateless JSON Streamable HTTP. A trusted LAN client can
connect directly. The optional OpenAI Secure MCP Tunnel connects outbound from
QNAP and forwards requests to the same private `/mcp` endpoint without exposing
port 8000 publicly.

## Credentials and errors

- Trading 212 credentials come only from `T212_API_KEY` and
  `T212_API_SECRET` environment variables.
- The settings object excludes credentials from its representation.
- HTTP Basic authentication is held in memory by `httpx`.
- Authorization headers, API keys, secrets, and upstream response bodies are
  not included in client-visible errors.
- Configuration, authentication, permission, timeout, rate-limit, network, and
  malformed-response failures use bounded messages without secret values.
- Unexpected exceptions become a generic internal-server error at the MCP
  boundary.

Treat all account, cash, portfolio, order, transaction, and dividend responses
as sensitive financial data even though they are read-only.

## Pagination and rate limiting

Historical tools retrieve exactly one page per call. A returned
`next_page_path` must be passed unchanged to the same tool. The client rejects
absolute URLs, other hosts, fragments, duplicate keys, undocumented query
keys, and paths belonging to a different endpoint.

The server performs no automatic retry after a 429 response. It may expose only
a numeric rate-limit reset timestamp when Trading 212 provides one. This avoids
infinite retries and unbounded request bursts.

## Container controls

Runtime, build and development dependencies are version-locked with SHA-256
artifact hashes. Docker verifies third-party hashes before installation and
installs the project wheel separately without resolving additional dependencies.
CI audits all three locks for known advisories and scans the runtime image for
high/critical OS and Python vulnerabilities on pull requests and weekly. It
reports all such image findings and blocks those with an available fix. Unfixed
base-image advisories remain visible for review; a green gate is not a clean
bill of health for the operating system.
See [dependency maintenance](development.md#security-review) for regeneration
and local audit commands. A passing scan describes the checked versions and
advisory database at that time; updates still require fresh checks.

The MCP image and Compose project use:

- a non-root runtime user with UID/GID 10001;
- a read-only root filesystem;
- a 16 MiB temporary `/tmp` filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- a local healthcheck;
- `restart: unless-stopped`; and
- no database; optional snapshot storage mounted read-only in the MCP service.

The optional collector writes only to its dedicated snapshot mount. It publishes
both CSVs by atomic directory rename under an exclusive lock. Files use mode
0600 and capture directories 0700; readers reject symlinks, non-regular files,
hard links, invalid schemas, and files over 32 MiB. CSV text is escaped against
spreadsheet formula execution. Treat CSVs and backups as private financial data.
Only collector timestamps and health state appear in operational status.
Instrument and exchange metadata are cached for ten minutes per credential and
environment; account data is never served from that cache.

The tunnel project uses the same non-root, read-only, capability-free controls,
pins the official image by digest, mounts its runtime key read-only, and
publishes no ports.

## Network boundary

Local Docker binds to `127.0.0.1` by default. QNAP deployment binds the MCP port
to one fixed NAS LAN address, not a wildcard address. Host and Origin validation
is enabled for Streamable HTTP.

The QNAP verifier checks every published mapping and requires one RFC 1918 IPv4
address across all mappings. It rejects wildcard, public, loopback, link-local,
IPv6, malformed and multiple-address bindings before MCP discovery. Compare
the accepted private address with the intended NAS address in Container Station.

The optional tunnel uses host networking only to reach the LAN-bound MCP
listener. Its health and admin service binds to `127.0.0.1:18080`, remote UI is
disabled, and no tunnel port is published. Do not create router forwarding,
public DNS, a public reverse proxy, or another public tunnel for ports 8000 or
18080. See the [QNAP deployment guide](qnap-deployment.md) and
[Secure MCP Tunnel guide](secure-mcp-tunnel.md).

## Verify the write surface

Run the automated security suite:

```bash
pytest tests/test_security.py -q
```

It enumerates MCP tools, inspects public client methods, and parses the client
AST to reject generic or mutating HTTP calls. A supplementary source search is:

```bash
rg -n -i '\.(post|put|patch|delete|request|send)\(|def (buy|sell|place|create_order|place_order|cancel|cancel_order|modify|modify_order|update_order)\b' src
```

The expected result is no match. The QNAP verifier also discovers the exact
fourteen tool names without invoking any financial tool and rejects write-like
names.
