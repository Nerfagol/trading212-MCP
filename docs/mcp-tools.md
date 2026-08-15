# MCP Tool Reference

The server exposes exactly eight Trading 212 read-only tools. Every tool has
MCP `readOnlyHint: true`, `destructiveHint: false`, and `openWorldHint: false`.
The annotations help an MCP client select tools, but the technical security
boundary is stronger: the API client contains only six allowlisted `GET`
paths and has no generic request or order-writing method.

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
