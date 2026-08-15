# Deployment-First README Design

## Goal

Make the public repository approachable to a new operator who wants to run the
read-only Trading 212 MCP server locally, on a QNAP LAN, or through OpenAI
Secure MCP Tunnel. Preserve the detailed reference documents while turning the
root README into a short deployment decision and verification path.

## Audience

The primary reader understands basic Docker commands but may not know MCP,
Trading 212 API environment rules, QNAP Container Station paths, or Secure MCP
Tunnel. The README must let that reader choose the correct deployment without
first reading implementation details.

## README Information Architecture

The README will use this order:

1. Project name and a two-sentence read-only summary.
2. A prominent safety statement describing the technical inability to trade.
3. A deployment chooser for local Docker, QNAP LAN-only, and QNAP plus Secure
   MCP Tunnel.
4. A local Docker quick start using Demo as the documented first-run default.
5. A QNAP quick start linking to the full operator runbook.
6. A ChatGPT tunnel quick start linking to the official OpenAI and project
   tunnel guides.
7. Verification commands for `/health`, MCP discovery, and the security tests.
8. The eight-tool summary and required Trading 212 read permissions.
9. The deployed architecture diagram showing the outbound tunnel path and
   optional direct trusted-LAN path.
10. A concise security architecture section.
11. A troubleshooting table for common deployment failures.
12. Links to detailed project documentation and official upstream resources.
13. Independence, disclaimer, and MIT license sections.

The existing long-form documents remain authoritative for detailed tool
schemas, QNAP lifecycle operations, and Secure MCP Tunnel setup. The README
will not duplicate their full content.

## Deployment Chooser

The chooser will be a compact table with three rows:

- Local Docker: for evaluation and development on one machine.
- QNAP LAN-only: for private use by trusted clients on the same LAN.
- QNAP plus Secure MCP Tunnel: for ChatGPT or another supported OpenAI product
  without exposing port 8000 publicly.

Each row will identify the endpoint scope, command entry point, and detailed
guide. No option will recommend wildcard binding, router forwarding, a public
reverse proxy, or a third-party tunnel.

## Quick Starts

### Local Docker

The local path will show cloning, copying `.env.example`, mode `600`, selecting
Demo or Live, `docker compose up -d --build`, `/health`, and MCP Inspector. It
will state that Demo and Live credentials are not interchangeable and that no
Trading 212 request occurs during the health check or tool discovery.

### QNAP LAN-Only

The QNAP path will show a persistent `/share/Container/trading212-mcp`
directory, a fixed NAS LAN binding, `deploy.sh mcp`, and `verify.sh mcp`. It
will link to `docs/qnap-deployment.md` before presenting tunnel steps.

### Secure MCP Tunnel

The tunnel path will show `prepare-secrets.sh init`, protected population,
`prepare-secrets.sh lock`, `deploy.sh tunnel`, and `verify.sh tunnel`. It will
explain that the client creates an outbound HTTPS route and that ChatGPT-side
discovery is completed when the custom app is created. It will link only to
current official OpenAI documentation for OpenAI product behavior.

## Tools and Permissions

The README will retain a compact table for exactly these tools:

- `get_account`
- `get_cash`
- `get_portfolio`
- `get_position`
- `get_orders`
- `get_order_history`
- `get_transactions`
- `get_dividends`

It will direct readers to `docs/mcp-tools.md` for arguments and structured
responses. Permission guidance will recommend only account data, portfolio,
history, and read-order access. It will explicitly advise against enabling
trading or order-management permissions when offered separately.

## Troubleshooting

The root troubleshooting table will include:

- HTTP 401: credentials do not match the selected Demo/Live environment.
- HTTP 403: the key lacks a required read permission.
- HTTP 421 from `/mcp`: the request host is missing from
  `MCP_ALLOWED_HOSTS`.
- MCP container unhealthy: inspect the container state and `/health` before
  attempting a Trading 212 tool call.
- Tunnel `/readyz` or doctor failure: confirm outbound HTTPS, private MCP
  reachability, tunnel association, and runtime-key Tunnels Read + Use.

Troubleshooting commands must not print `.env`, raw tunnel logs, account data,
or credentials.

## Official Trading 212 Agent Skills Reference

The README will link to
`https://github.com/trading212-labs/agent-skills` in a related official
resources section. The relationship statement will say:

- the official repository informed endpoint and behavior research;
- this project is independent and is not endorsed by Trading 212;
- this project neither imports nor depends on agent-skills; and
- agent-skills includes trading actions, whereas this project deliberately
  implements only allowlisted GET operations.

The project will not copy agent-skills source or imply official status.

## License and Disclaimer

Add a root `LICENSE` containing the standard MIT License with:

```text
Copyright (c) 2026 Nerfagol
```

The README will link to `LICENSE` and state that the software is provided under
MIT. It will include a concise disclaimer that the project is not financial
advice, is not affiliated with or endorsed by Trading 212, and that Trading 212
names and trademarks belong to their respective owner.

## Verification

Add documentation regression tests that require:

- the deployment chooser and all three deployment paths;
- links to the three detailed guides;
- the exact eight-tool set;
- the outbound tunnel and LAN-only architecture wording;
- the official agent-skills URL and independence statement; and
- a standard MIT `LICENSE` with the approved copyright line.

Run the full pytest suite, Ruff, mypy, package build, shell parsing, credential
scans, and Compose validation before pushing. No real Trading 212 call is
required for a documentation-only change.
