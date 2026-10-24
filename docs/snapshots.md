# Four-hour CSV snapshots

The optional collector saves account totals and current positions on your NAS.
The MCP service reads those files through `list_snapshots` and `get_snapshot`,
using the same connection as the live tools. This feature requires a source build;
the published 0.1.0 image does not include it.

## Enable on QNAP

Complete the [QNAP setup](qnap-deployment.md), including the protected root `.env`
and fixed NAS LAN binding. From the project directory, create a dedicated data
directory. Run ownership commands with the NAS privileges needed for that directory:

```sh
mkdir -p data/snapshots
chown 10001:10001 data/snapshots
chmod 700 data/snapshots
./deploy/qnap/deploy.sh snapshots
./deploy/qnap/verify.sh snapshots
```

The overlay mounts this directory at `/snapshots`: writable only in the collector,
read-only in the MCP container. The collector publishes no ports. Both containers
keep the non-root user, read-only root filesystem, dropped capabilities, and
`no-new-privileges`. No NAS deployment is performed by merely building the project.

For another dedicated host location, set `T212_SNAPSHOT_HOST_DIR` to its absolute
path in the protected root `.env`, and create it with the ownership above. Avoid
symlinks. Do not use a shared public folder or the project's source directory.
The directory must already exist; Compose will not silently create it as root.

For local Docker, use the same directory preparation and:

```sh
docker compose -f docker-compose.yml -f docker-compose.snapshots.yml up -d --build
```

For updates, run `./deploy/qnap/update.sh snapshots`. The `mcp` and `all` script
targets also preserve the overlay when the collector container exists. If it has
been removed, use the explicit `snapshots` target again. When invoking Compose
directly, always include both files. Update the independent tunnel separately.

## Schedule and gaps

Captures run at 00:00, 04:00, 08:00, 12:00, 16:00, and 20:00 UTC, within the
collector's 30-second polling interval. On startup it captures the current slot
if missing. Completed slots are not duplicated across restarts. Missed historical
slots are never backfilled; current quotes cannot reconstruct past observations.
On a failed attempt, the process waits for the next slot. Restarting allows a
retry of the current incomplete slot.

UTC scheduling does not shift with daylight saving. MCP summaries additionally
provide `captured_at_london` with the correct Europe/London offset. Account and
position requests are sequential, so the capture records its start and completion
times rather than claiming both responses represent exactly the same instant.

## Tables

Each completed capture has a directory under `demo/` or `live/`, named with its
UTC completion time (`YYYYMMDDTHHMMSSffffffZ`). It contains exactly two CSV files:

| File | Columns |
| --- | --- |
| `summary.csv` | `schema_version`, `snapshot_id`, `scheduled_for_utc`, `capture_started_at_utc`, `captured_at_utc`, `environment`, `account_currency`, `total_account_value`, `position_count` |
| `positions.csv` | `snapshot_id`, `ticker`, `name`, `quantity`, `current_price`, `price_currency` |

Schema version is `1`. The total is Trading 212's account `totalValue`, in account
currency. Each price keeps the instrument's upstream currency or quotation unit;
no currency conversion or guessed position value is calculated. Decimal precision
is retained in CSV and exposed as strings over MCP. Empty portfolios still produce
a summary and a positions header. Potential spreadsheet formulas in text are
escaped with an apostrophe; MCP reverses that escaping.

There are no cost, P/L, order, dividend, transaction, or pie tables in these snapshots.
The live tools continue to provide those supported reads independently.

## Read with MCP

Ask the connected client to list saved snapshots, then read a selected snapshot.
`list_snapshots` supports inclusive timezone-aware start/end dates and cursor
pagination. `get_snapshot` pages positions by offset. See the
[tool reference](mcp-tools.md) for parameter limits. The tools only read saved CSVs;
they cannot start a capture, edit files, or make a Trading 212 request.

After upgrading, refresh your MCP client's tool list. Unconfigured storage returns
a clear error; an empty configured directory returns an empty snapshot list.

## Storage and operations

Snapshots remain until you manually remove them. Monitor NAS capacity and use
private backups; the service performs no retention deletion. `data/` is excluded
from Git, Docker contexts, and source distributions. Credentials are never saved
in snapshot files. The private `.account` fingerprint binds each environment
directory to one account. Keep it when retaining snapshots; use a different root
directory if switching accounts. Rotating credentials for the same account is safe.

The writer holds an exclusive lock and publishes both CSVs together by directory
rename. Incomplete `.pending-*` directories are ignored after an interrupted write.
Files are private (0600), capture directories are 0700, and each CSV is limited to
32 MiB. Invalid or incomplete captures produce bounded errors rather than partial
position results. Do not modify captures while they are being read.

The collector healthcheck reads only local status. It requires a heartbeat within
two minutes, a successful capture within eight hours, and no failed latest attempt.
Operational status includes timestamps and state, never holdings or account values.
Docker marks failures unhealthy; it does not automatically restart unhealthy
containers. Check directory ownership, free space, and API read permissions, then
restart the collector if a current-slot retry is wanted. The MCP `/health` endpoint
remains independent of collection health.
