# Deploying BlackBox

From `make demo` to a production instance. Every knob referenced here
is detailed in the [configuration reference](./configuration.md).

## The short version

```bash
# 1. Postgres instead of SQLite (migrations run automatically on start)
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build

# 2. Turn authentication on
BLACKBOX_API_TOKENS=$(openssl rand -hex 24)
NEXT_PUBLIC_BLACKBOX_API_TOKEN=$BLACKBOX_API_TOKENS   # baked into the web build
```

## Database

- **SQLite** (default) is right for a single facility on one machine;
  the `blackbox-data` volume holds everything.
- **Postgres** is the production path: set
  `BLACKBOX_DATABASE_URL=postgresql+psycopg://…` and install
  `apps/api[postgres]` (the compose override does both). Startup runs
  Alembic migrations either way — a database created by an older
  BlackBox is upgraded in place, which is why backups come first.

## Authentication tiers

| Tokens | Who gets them |
| --- | --- |
| `BLACKBOX_API_TOKENS` | Robots, the web deployment, operators' CLIs. |
| `BLACKBOX_READONLY_TOKENS` | Wallboards, dashboards, viewers. |
| `BLACKBOX_FACILITY_TOKENS` | One shared instance serving several facilities: each token is isolated to its facility across every read, write, stream, and export. |

The web app's token (`NEXT_PUBLIC_BLACKBOX_API_TOKEN`) is baked into
the bundle at build time — it keeps strangers on the network out of the
API, not the token out of the app's users. Streaming robots pass theirs
via `?token=` or headers.

## Internet exposure

BlackBox's own hardening (tokens, upload cap,
`BLACKBOX_RATE_LIMIT_PER_MINUTE`) targets a trusted-network deployment
with guardrails. For anything internet-facing, put a reverse proxy
(TLS, real rate limiting, request size limits) in front and treat the
instance as experimental — see [SECURITY.md](../SECURITY.md).

## Day-2 operations

- **Backups**: `blackbox backup ./dump` captures every incident with
  its analysis, verdict, and notes through the public API;
  `blackbox restore` replays them into a fresh instance (analyses
  recompute deterministically). Database-level backups work too — the
  schema is plain SQL.
- **Retention**: cron `blackbox prune --days 90 --yes` (facility-scoped
  tokens prune only their own facility).
- **Alerting**: `BLACKBOX_WEBHOOK_URL` posts every diagnosis to a
  Slack-compatible endpoint, flagging recurring signatures by
  occurrence number.
- **Health**: `GET /health` (open, for probes) reports the app version,
  migration revision, and incident count; `blackbox doctor` checks
  connectivity, versions, and auth in one command.
- **Monitoring the fleet from a shell**: `blackbox watch`.

## Upgrades

1. `blackbox backup` (or snapshot the database).
2. Deploy the new build; migrations run on startup.
3. `blackbox doctor` — it flags CLI/server version skew and verifies
   the database revision.
