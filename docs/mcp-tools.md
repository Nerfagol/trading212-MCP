# MCP Tool Reference

The server exposes exactly fourteen read-only tools. Every tool has
MCP `readOnlyHint: true`, `destructiveHint: false`, and `openWorldHint: false`.
The annotations help an MCP client select tools, but the technical security
boundary is stronger: the API client contains nine fixed `GET` paths plus a
constrained numeric pie-ID path and has no generic request or order-writing method.
Two tools read local snapshots without contacting Trading 212.

## Tool index

| Tool | Use it for | Arguments | Trading 212 request |
| --- | --- | --- | --- |
| `get_account` | Complete account overview | none | `GET /api/v0/equity/account/summary` |
| `get_cash` | Cash and buying-power questions | none | `GET /api/v0/equity/account/summary` |
| `get_portfolio` | Every open position | none | `GET /api/v0/equity/positions` |
| `get_position` | One exact instrument | `ticker` | `GET /api/v0/equity/positions` |
| `get_orders` | Active pending orders | none | `GET /api/v0/equity/orders` |
| `get_order_history` | Historical orders and fills | `limit`, `ticker`, `next_page_path` | `GET /api/v0/equity/history/orders` |
| `get_transactions` | Deposits, withdrawals, fees, and transfers | `limit`, `next_page_path` | `GET /api/v0/equity/history/transactions` |
| `get_dividends` | Paid dividends | `limit`, `ticker`, `next_page_path` | `GET /api/v0/equity/history/dividends` |
| `search_instruments` | Find an instrument | `query`, `limit` | `GET /api/v0/equity/metadata/instruments` |
| `get_exchanges` | Exchange metadata | none | `GET /api/v0/equity/metadata/exchanges` |
| `get_pies` | Existing pies | none | `GET /api/v0/equity/pies` |
| `get_pie` | Pie details | `pie_id` | `GET /api/v0/equity/pies/{id}` |
| `list_snapshots` | Saved totals and times | `start`, `end`, `cursor`, `limit` | Local CSV only |
| `get_snapshot` | Saved positions | `snapshot_id`, `offset`, `limit` | Local CSV only |

Trading 212 API permissions are configured when the key is generated. Enable
only account data, portfolio, history, and read-order access needed by the
tools you intend to use. Do not enable trading or order-management permission
when it is offered separately.

## `get_account`

Use this for a broad account summary. It takes no arguments and returns the
validated Trading 212 account-summary object, including:

- `id`: numeric account identifier;
- `currency`: primary account currency;
- `totalValue`: total account value;
- `cash`: `availableToTrade`, `reservedForOrders`, and `inPies`; and
- `investments`: current value, total cost, realized P/L, and unrealized P/L.

Likely permission: account data. This tool does not list individual positions.

## `get_cash`

Use this instead of `get_account` when the request is specifically about cash
or buying power. It takes no arguments and returns only:

```json
{
  "currency": "GBP",
  "availableToTrade": 123.45,
  "reservedForOrders": 10.0,
  "inPies": 5.0
}
```

The numbers above are fictional. This tool projects fields from the documented
account-summary response; it does not call a separate or uncertain cash path.
Likely permission: account data.

## `get_portfolio`

Use this for all currently open positions. It takes no arguments and returns:

```json
{
  "positions": []
}
```

Each entry is a Trading 212 position object containing the instrument, quantity,
pricing, value, cost, and unrealized P/L data supplied by the API. An empty array
means there are no open positions. Likely permission: portfolio.

## `get_position`

Use this when one exact Trading 212 instrument is named. The required `ticker`
is case-sensitive, 1 to 100 characters, and must be the Trading 212 ticker rather
than a display symbol. For example, use the synthetic selection argument:

```json
{"ticker": "AAPL_US_EQ"}
```

The response uses the same `positions` array wrapper as `get_portfolio`; it is
empty when no matching open position exists. Likely permission: portfolio.

## `get_orders`

Use this to read current active or pending orders and execution state. It takes
no arguments and returns `{"orders": [...]}`. The returned objects come from
Trading 212's current-order API. Likely permission: read orders.

This tool cannot change or cancel an order. If Trading 212 bundles order reads
with a broader permission and least privilege is preferred, leave that
permission disabled; only this tool should then return a permission error.

## `get_order_history`

Use this for past orders and fills. Arguments:

| Argument | Required | Meaning |
| --- | --- | --- |
| `limit` | no | Items requested, integer 1 through 50; default 20 |
| `ticker` | no | Exact Trading 212 ticker filter |
| `next_page_path` | no | Opaque path returned by the preceding call |

The response is `{"items": [...], "next_page_path": null}` or contains a
string path for the next page. Likely permission: history.

## `get_transactions`

Use this for cash movements such as deposits, withdrawals, fees, and transfers.
It accepts `limit` and `next_page_path` with the same rules as order history and
returns the same page wrapper. Likely permission: history.

## `get_dividends`

Use this for paid dividends. It accepts `limit`, optional exact `ticker`, and
`next_page_path`, and returns the standard page wrapper. Likely permission:
history.

## `search_instruments`

Search ticker, name, or ISIN with a trimmed, case-insensitive `query` of 1–100
characters. `limit` is 1–50, default 20. Exact ticker and ISIN matches rank first,
then results sort by ticker. Returns `instruments`, `total_matches`, and `truncated`.
Successful metadata is cached for ten minutes; expired data is not served on failure.

## `get_exchanges`

Returns `exchanges` with upstream metadata and working schedules. Takes no
arguments and uses the same ten-minute metadata cache. These are schedules,
not a live market-open indicator.

## `get_pies`

Returns `pies` from the account. Takes no arguments. Trading 212 marks the pies
API deprecated, so availability depends on the upstream service and permissions.
No tool creates, edits, funds, rebalances, or imports holdings into pies.

## `get_pie`

Reads a single pie's `settings` and `instruments`. Required `pie_id` must be a
positive integer below 2^63. This uses the deprecated pies API, with safe errors
when unavailable.

## `list_snapshots`

Lists completed local snapshots newest first, with totals, account currency,
position count, UTC capture times, and a Europe/London display timestamp.
Optional inclusive `start` and `end` must be timezone-aware ISO timestamps.
`limit` is 1–50 (default 20); pass the returned `next_cursor` as `cursor` for
the next page, keeping the same date filters. Returns `snapshots` and `next_cursor`.
An initialized store with no captures returns an empty list; unconfigured storage
returns a bounded error. No credentials or Trading 212 requests are needed.

## `get_snapshot`

Required `snapshot_id` comes from `list_snapshots`. Returns `summary`, `positions`,
and `next_offset`. `offset` starts at zero; `limit` is 1–200 (default 100).
Quantities, current prices, and totals are decimal strings to preserve precision.
These are historical observations, not current quotes. Account totals and position
prices can use different currencies; do not add prices or convert implicitly.
See [CSV snapshots](snapshots.md) for setup, schemas, scheduling, and retention.

## Pagination

Historical tools deliberately fetch one page per MCP call. When
`next_page_path` is non-null:

1. Pass it unchanged to the same tool that returned it.
2. Do not combine it with a path from another historical tool.
3. Keep `limit` within 1 through 50.

The client rejects absolute URLs, other hosts, fragments, duplicate query keys,
unknown query keys, and paths for another endpoint. It performs no automatic
infinite pagination or retry loop.

## Errors

Tools return safe errors for invalid configuration, authentication failure,
missing read permission, timeout, rate limiting, malformed data, or an invalid
pagination path. Upstream bodies, Authorization headers, API keys, and secrets
are never included in those errors.

## Forbidden capabilities

There is no tool for buying, selling, placing, creating, cancelling, modifying,
or updating an order. The deployment verifier rejects names containing `buy`,
`sell`, `place`, `create_order`, `place_order`, `cancel`, `cancel_order`,
`modify`, `modify_order`, or `update_order`.
