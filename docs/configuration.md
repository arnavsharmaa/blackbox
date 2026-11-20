# Configuration reference

Every environment variable BlackBox reads, in one place. All are
optional — an unconfigured instance runs the zero-config
trusted-network setup (`make demo`). Values can also live in a `.env`
file (see [.env.example](../.env.example)).

Kept honest by `apps/api/tests/test_config_docs.py`, which fails if a
settings field is missing from this page.

## Core (`BLACKBOX_*`)

| Variable | Default | Purpose |
| --- | --- | --- |
| `BLACKBOX_DATABASE_URL` | `sqlite:///./data/blackbox.db` | SQLAlchemy database URL. Postgres: `postgresql+psycopg://user:pass@host:5432/db` (install `apps/api[postgres]`). |
| `BLACKBOX_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call the API. |
| `BLACKBOX_API_HOST` | `0.0.0.0` | Bind host for uvicorn (Makefile / compose). |
| `BLACKBOX_API_PORT` | `8000` | Bind port for uvicorn. |
| `BLACKBOX_MAX_UPLOAD_MB` | `20` | Upload size cap; raise for long recordings. |
| `BLACKBOX_API_TOKENS` | *(empty)* | Comma-separated full-access tokens. Any token list being set turns authentication on. |
| `BLACKBOX_READONLY_TOKENS` | *(empty)* | Comma-separated GET-only tokens for wallboards and dashboards. |
| `BLACKBOX_FACILITY_TOKENS` | *(empty)* | JSON object mapping token → facility name; each token reads and writes only that facility (multi-tenancy). |
| `BLACKBOX_STREAM_WINDOW_S` | `600` | Rolling pre-failure window per streaming robot, seconds. |
| `BLACKBOX_RATE_LIMIT_PER_MINUTE` | `0` | Non-GET requests per client IP per minute; `0` disables. |
| `BLACKBOX_WEBHOOK_URL` | *(empty)* | Slack-compatible webhook POSTed for every ingested incident (best-effort). |
| `BLACKBOX_EXTRA_RULES` | *(empty)* | Comma-separated `module:function` analysis-rule plug-ins ([examples](../examples/rules)). |

## Analysis thresholds (`BLACKBOX_RULE_*`)

Per-deployment tuning of the deterministic rules; overridden values flow
into evidence text and the replay's threshold guides.

| Variable | Default | Rule | Meaning |
| --- | --- | --- | --- |
| `BLACKBOX_RULE_OBSTACLE_SAFETY_THRESHOLD_M` | `0.6` | obstacle | Clearance below this counts as blocked. |
| `BLACKBOX_RULE_OBSTACLE_BLOCKAGE_MIN_S` | `5.0` | obstacle | Blocked interval must last this long. |
| `BLACKBOX_RULE_ZERO_CMD_EPS` | `0.01` | obstacle | Velocities below this are "zero". |
| `BLACKBOX_RULE_ZERO_CMD_STREAK_MIN` | `5` | obstacle | Consecutive zero commands required. |
| `BLACKBOX_RULE_RECOVERY_ATTEMPTS_MIN` | `2` | obstacle | Recovery behaviors required. |
| `BLACKBOX_RULE_RECOVERY_DISPLACEMENT_MAX_M` | `0.3` | obstacle | Max displacement across recoveries. |
| `BLACKBOX_RULE_LOC_CONF_HEALTHY_MIN` | `0.9` | obstacle | Localization at/above this adds exculpatory evidence. |
| `BLACKBOX_RULE_LOC_CONF_FAULT` | `0.5` | localization | Confidence below this is a fault. |
| `BLACKBOX_RULE_LOC_CONF_DROP` | `0.4` | localization | Sudden drop within 5 s that counts. |
| `BLACKBOX_RULE_POSE_JUMP_M` | `1.0` | localization | Pose jump between samples that counts. |
| `BLACKBOX_RULE_ANGULAR_FLIP_MIN_RAD_S` | `0.3` | oscillation | \|ω\| for a command to count as a flip. |
| `BLACKBOX_RULE_ANGULAR_FLIPS_MIN` | `8` | oscillation | Sign flips required. |
| `BLACKBOX_RULE_FLIP_PROGRESS_MAX_M` | `0.5` | oscillation | Max forward progress in the flip window. |
| `BLACKBOX_RULE_FLIP_MEAN_SPEED_MAX` | `0.15` | oscillation | Max mean speed in the flip window. |
| `BLACKBOX_RULE_REPLAN_MIN` | `2` | oscillation | Replans required. |
| `BLACKBOX_RULE_SENSOR_GAP_FACTOR` | `5.0` | dropout | Gap counts at this multiple of the median interval. |
| `BLACKBOX_RULE_SENSOR_GAP_MIN_S` | `2.0` | dropout | Absolute minimum gap, seconds. |

## Optional AI summaries

Never used to determine the root cause; requires `pip install -e
"apps/api[ai]"`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | *(unset)* | Enables AI summaries via the Anthropic API (preferred). |
| `OPENAI_API_KEY` | *(unset)* | Fallback provider. |
| `BLACKBOX_AI_ANTHROPIC_MODEL` | `claude-opus-5` | Anthropic model override. |
| `BLACKBOX_AI_OPENAI_MODEL` | `gpt-4o` | OpenAI model override. |

## Web app (build-time)

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Where the browser reaches the API. |
| `NEXT_PUBLIC_BLACKBOX_API_TOKEN` | *(unset)* | Token the web app sends when auth is on. Public by design: it gates the network, not the app's users. |
| `NEXT_PUBLIC_GITHUB_REPO` | *(unset)* | Default `owner/repo` for prefilled issue URLs. |

## CLI

| Variable | Default | Purpose |
| --- | --- | --- |
| `BLACKBOX_API_URL` | `http://localhost:8000` | Instance the `blackbox` CLI talks to. |
| `BLACKBOX_API_TOKEN` | *(unset)* | Token the CLI sends. |
