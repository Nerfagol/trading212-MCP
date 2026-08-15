# User-Friendly README Design

**Date:** 2026-08-15
**Status:** Approved

## Goal

Make the public repository understandable to both first-time self-hosters and
technical operators. The README should explain what the product enables before
asking readers to choose a deployment path, while preserving a visible and
accurate read-only security contract.

## Audience

The primary audience is a mixed group:

- users who want to ask ChatGPT about their Trading 212 account without first
  understanding MCP internals; and
- operators who need a quick route to local Docker or QNAP deployment.

The opening should use plain language. Technical terminology remains available
where it helps users make a deployment or security decision.

## Content Strategy

Use a product-first, progressive structure:

1. Explain what the server lets a user do.
2. Show realistic example questions.
3. State the read-only boundary prominently.
4. Set expectations about tools, output, and the lack of a web interface.
5. Present the three supported deployment choices.
6. Provide only the minimum commands required to start and verify a deployment.
7. Link to focused documentation for operational and implementation detail.

The copy should be descriptive rather than promotional. It must not imply that
the server gives investment advice, performs portfolio analytics beyond the API
data it returns, or supports any trading action.

## README Structure

The top portion should follow this order:

1. Repository title and one-paragraph product summary.
2. `📊 What this gives you` with concise capability bullets.
3. `💬 Example questions` with realistic prompts for account, cash, positions,
   orders, transactions, and dividends.
4. `🔒 Read-only by design` with the fixed GET-only boundary.
5. `✅ What to expect` covering eight MCP tools, Demo/Live support, structured
   responses, health checking, and the absence of a web UI.
6. `🚀 Choose your deployment` comparing local Docker, QNAP LAN-only, and QNAP
   with OpenAI Secure MCP Tunnel.

The remaining README should contain short onboarding sections, the eight-tool
summary, links to detailed documentation, official resources, disclaimer, and
license.

## Emoji Style

Use emojis moderately:

- one emoji on major product and onboarding headings;
- optional emojis in the deployment chooser where they improve scanning;
- no emoji on every subsection, command, table row, note, or status message.

Emojis must not replace meaningful text or security wording.

## README and Documentation Boundary

The README retains:

- product purpose and example questions;
- the prominent read-only guarantee;
- deployment chooser;
- one short local Docker quick start;
- short QNAP and tunnel entry points;
- exact eight-tool summary;
- minimal health and discovery verification; and
- links to focused guides.

Detailed documentation retains or receives:

- full environment-variable reference;
- Trading 212 permission guidance;
- endpoint, pagination, arguments, and response behavior;
- architecture internals and complete security implementation;
- QNAP configuration, deployment, updates, and rollback;
- tunnel secret preparation and troubleshooting; and
- development, testing, linting, type checking, and package build commands.

Existing guides remain authoritative:

- `docs/mcp-tools.md`
- `docs/qnap-deployment.md`
- `docs/secure-mcp-tunnel.md`
- `deploy/qnap/README.md`

## Product Expectations

The README should explicitly tell users:

- the server exposes MCP tools, not a browser dashboard;
- it returns structured Trading 212 account data to the connected MCP client;
- it supports Invest and Stocks ISA data available through the API;
- Demo is the recommended first-run environment;
- Live mode reads real account data but adds no write capability;
- historical results are paginated; and
- account and portfolio output is sensitive even though the server is
  read-only.

Example questions must map directly to an implemented tool. Avoid promising
calculations, forecasting, tax reporting, alerts, or functionality that would
require additional code.

## Security Contract

The README must continue to state that:

- the client contains only six allowlisted Trading 212 GET endpoints;
- exactly eight read-only MCP tools are exposed;
- no buy, sell, create, place, cancel, modify, or update-order implementation
  exists;
- no generic HTTP request method exists; and
- QNAP deployment remains LAN-only unless the outbound OpenAI Secure MCP Tunnel
  is intentionally configured.

Detailed implementation controls may be linked from the README rather than
repeated there. Security wording must remain precise and must not rely on MCP
annotations as the technical boundary.

## Testing

Update documentation contract tests to verify:

- the product-first sections appear before deployment instructions;
- example questions cover only implemented read-only capabilities;
- the deployment chooser and required entry-point commands remain present;
- the exact tool surface and read-only statements remain present; and
- every local documentation link resolves.

Run the full test, lint, type-check, build, shell-syntax, and publication
security checks before pushing the README change.

## Non-Goals

- No application, MCP tool, deployment, or container behavior changes.
- No screenshots, generated artwork, feature badges, or marketing claims.
- No Claude connection instructions until that path is tested end to end.
- No new public exposure, authentication protocol, or network service.
- No removal of the detailed operational guides.
