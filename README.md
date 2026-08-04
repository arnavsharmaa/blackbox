# BlackBox

**BlackBox reconstructs robot failures from telemetry, planner decisions, sensor streams, and controller actions—then produces a replayable, evidence-backed incident report.**

BlackBox is a flight recorder and incident-reconstruction platform for
autonomous robots. When a navigation task fails, it answers the questions an
engineer actually asks:

- What was the robot trying to do?
- What happened immediately before the failure?
- Which subsystem likely caused it — and what evidence supports that?
- What should be investigated next?
- Can the incident be replayed deterministically?

Root-cause detection is **deterministic and rules-based**: every diagnosis is
backed by timestamped evidence you can click to jump the replay to. An
optional LLM layer can summarize the analysis, but it never determines the
root cause and the product is fully useful without any API key.

| Incident overview | Incident replay |
| --- | --- |
| _dashboard: fleet stats, filters, failure-category breakdown_ | _synchronized timeline, telemetry cursors, 2D path map, evidence panel_ |

> Screenshots: run `make demo` and open http://localhost:3000 — the seeded
> primary incident (`INC-2026-0728-001`) is the demo scenario below.

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        R[ROS 2 topics / rosbag2] -.future adapter.-> ING
        J[Incident JSON] --> ING
        C[Normalized CSV events] --> ING
        S[Seed script] --> ING
    end

    subgraph "apps/api — FastAPI"
        ING[Ingestion adapters<br/>validate → canonical schema] --> DB[(SQLite<br/>incidents · events · telemetry · analyses)]
        ING --> AN[Deterministic analysis engine<br/>4 weighted rules → evidence]
        AN --> DB
        DB --> API[REST API<br/>/api/incidents/*]
        AN -. optional, labeled .-> AI[AI summary<br/>Anthropic API]
    end

    subgraph "apps/web — Next.js"
        API --> OV[Overview dashboard]
        API --> DET[Incident detail<br/>replay · timeline · charts · map]
        API --> REP[Report view]
        API --> GH[GitHub issue preview]
    end

    SCH[packages/schemas<br/>canonical schema: Pydantic ⇄ TypeScript] --- ING
    SCH --- DET
```

**Boundaries:** ingestion (adapters) → analysis (pure rules over derived
features) → storage (SQLAlchemy repository) → API (FastAPI routers). The
frontend consumes the API only. One canonical incident schema is defined in
Pydantic ([apps/api/blackbox_api/schemas/incident.py](apps/api/blackbox_api/schemas/incident.py)),
mirrored in TypeScript ([packages/schemas/src/incident.ts](packages/schemas/src/incident.ts)),
exported as JSON Schema ([packages/schemas/incident.schema.json](packages/schemas/incident.schema.json)),
and guarded against drift by
[a sync test](apps/api/tests/test_schema_sync.py).

## Core features

- **Deterministic root-cause analysis** — four rules (persistent obstacle,
  localization failure, controller oscillation, sensor dropout) score
  weighted conditions over derived features; each diagnosis returns a
  confidence, evidence anchored to timestamps, recommended investigation
  steps, and the alternative causes considered.
- **Deterministic replay** — play/pause, 0.5×–4× speed, scrubbing, jump to
  failure, optional auto-pause at the failure moment. The replay clock drives
  the timeline cursor, five synchronized telemetry charts, the 2D path map,
  the system-health panel, and the event inspector from one store.
- **Evidence you can click** — every evidence item seeks the replay to the
  moment it describes.
- **Incident reports** — executive summary, metadata, root cause, evidence,
  key timeline, telemetry extremes, reproduction notes; copy as Markdown,
  download as JSON, print view.
- **GitHub issue generation** — complete issue Markdown (repro steps,
  expected/actual, evidence, investigation list) with copy, download, and a
  prefilled `github.com/.../issues/new` URL. No OAuth needed.
- **Ingestion with useful errors** — JSON and normalized-CSV uploads are
  validated against the canonical schema; malformed input returns
  field-level errors (HTTP 422), never a stack trace.
- **ROS 2 bag ingestion** — upload a rosbag2 MCAP recording directly
  (`ros2 bag record -s mcap`); decoding is pure Python, so ROS is *not*
  required to run BlackBox. Plus a documented adapter interface, topic
  mapping, and an example live recorder node. `make demo-bag` generates a
  sample bag to try.

## Demo scenario

The primary seeded incident `INC-2026-0728-001` reconstructs warehouse robot
**W-104** failing a delivery to **Loading Bay B**:

1. W-104 receives the navigation goal and drives normally down aisle
   corridor C.
2. A pallet blocks the route; obstacle clearance drops below the 0.60 m
   safety threshold.
3. The local planner can't find a collision-free trajectory; the controller
   holds zero velocity (22 consecutive zero commands).
4. Three recovery behaviors run — rotate_in_place, backup, wait_and_retry —
   and all fail; displacement across them is 0.04 m.
5. A global replan finds no alternate route. Localization stays above 95%
   the whole time.
6. The task times out at t=90 s and fails.

**Deterministic diagnosis:** persistent obstacle blockage (95% confidence,
7 evidence items) — the robot correctly stopped rather than issuing unsafe
motion; localization is explicitly ruled out with exculpatory evidence.

Three more incidents exercise the other rules: a localization-confidence
collapse next to reflective racking (`…-002`), controller oscillation in a
0.78 m doorway (`…-003`), and a 22 s lidar dropout (`…-004`). All sample data
is generated deterministically — fixed timestamps, no randomness — by
[packages/sample-data/generate.py](packages/sample-data/generate.py).

## Quick start

Prerequisites: Python ≥ 3.11, Node ≥ 20, `make`. (Or use
[Docker](#docker-setup) instead.)

```bash
make setup   # venv + backend deps + npm install
make demo    # seed the 4 sample incidents, start API (:8000) + web (:3000)
```

Open **http://localhost:3000**, click into
**“Deliver pallet to Loading Bay B”**, and press **Play**.

## Local development

| Command | What it does |
| --- | --- |
| `make setup` | Create `.venv`, install backend (`apps/api[dev]`) and frontend deps |
| `make seed` | Regenerate deterministic sample incidents and load them |
| `make dev` | Run API (uvicorn, port 8000) and web (Next.js, port 3000) together |
| `make api` / `make web` | Run one side with reload |
| `make test` | Backend pytest + frontend vitest |
| `make lint` | ruff + mypy (strict) + eslint + `tsc --noEmit` |
| `make build` | Production build of the frontend |
| `make smoke` | End-to-end smoke test against a running stack |
| `make schema` | Re-export the JSON Schema from the Pydantic models |

Copy `.env.example` to `.env` to override defaults (database path, CORS,
API URL, optional AI key). Database initialization is repeatable: tables are
created on startup and `make seed` upserts the sample incidents.

## Docker setup

```bash
docker compose up --build
```

- `api` seeds the database on start, serves on `:8000`, with a `/health`
  healthcheck.
- `web` builds the production bundle and serves on `:3000` once the API is
  healthy.

Data persists in the `blackbox-data` volume. (Compose files are included in
the repo; they were authored against Docker Compose v2 but this machine's
checkout was validated via the local `make demo` path.)

## API

Interactive docs at http://localhost:8000/docs.

| Endpoint | Description |
| --- | --- |
| `GET /health` | Service, schema, and engine status |
| `GET /api/incidents` | Paginated list; filters: `robot_id`, `severity`, `outcome`, `failure_category`, `start_after`, `start_before`, `limit`, `offset` |
| `GET /api/incidents/{id}` | Full incident + stored analysis |
| `GET /api/incidents/{id}/events` | Events; filters: `event_type`, `severity` |
| `GET /api/incidents/{id}/telemetry` | Telemetry series; filter: `channel` |
| `GET /api/incidents/{id}/analysis` | Deterministic analysis (`?ai=true` attaches a labeled AI summary if a key is configured) |
| `POST /api/incidents/{id}/reanalyze` | Re-run the rules engine |
| `GET /api/incidents/{id}/report` | Structured report + Markdown |
| `GET /api/incidents/{id}/github-issue` | Issue title/body/labels (`?repo=owner/repo` adds a prefilled URL) |
| `POST /api/incidents/upload` | Multipart upload of `.json` (full incident), `.csv` (events + `metadata` form field), or `.mcap` (ROS 2 bag + `metadata` with at least `id` and `robot_id`) |

Invalid uploads return `422` with `{"message", "errors": [{field, error, input_preview}]}`.

## Incident schema

An incident is one failed (or notable) task execution:

- **Metadata** — id, robot id/model, facility, task name/goal, start/end
  time, outcome (`success | failed | timed_out | aborted`), severity,
  software & map versions, environment, summary.
- **Events** — timestamped, typed (`task_started`, `nav_goal_issued`,
  `pose_updated`, `velocity_command`, `planner_state_changed`,
  `obstacle_distance_updated`, `recovery_started`, `recovery_completed`,
  `warning_raised`, `error_raised`, `task_timed_out`, `task_failed`) with
  source subsystem, severity, message, structured payload, correlation id,
  and evidence tags.
- **Telemetry** — typed series (`pos_x`, `pos_y`, `heading`,
  `linear_velocity`, `angular_velocity`, `obstacle_distance`,
  `goal_distance`, `localization_confidence`, `planner_state`,
  `recovery_count`, `battery_pct`) sampled as `t` seconds from start.

Validation enforces event ordering within the incident window, per-channel
sample types and ordering, and no duplicate channels. See the
[JSON Schema](packages/schemas/incident.schema.json) for the exact contract.

## Analysis rules

Each rule scores weighted conditions computed from derived features
([features.py](apps/api/blackbox_api/analysis/features.py)); the top rule
above a 0.5 threshold wins, capped at 95% confidence, with the rest reported
as alternatives. No LLM is involved.

| Rule | Key conditions |
| --- | --- |
| `persistent_obstacle_blockage` | clearance < 0.60 m for ≥ 5 s · ≥ 5 consecutive zero-velocity commands · ≥ 2 recovery attempts · displacement < 0.3 m during recoveries · goal still active · timeout. Adds exculpatory evidence when localization stayed ≥ 90%. |
| `localization_failure` | confidence < 0.5 · drop > 0.4 within 5 s · pose jump > 1 m between samples · planner in `waiting_for_localization` · navigation failure |
| `controller_oscillation` | ≥ 8 angular-command sign flips (\|ω\| ≥ 0.3 rad/s) · forward progress < 0.5 m in the window · ≥ 2 replans · mean speed < 0.15 m/s · task not completed |
| `sensor_dropout` | sensor gap > max(5× median interval, 2 s) · stale-timestamp diagnostics · planner degraded after the gap · task not completed |

If nothing clears the threshold the result is `unknown` with manual-review
guidance — the engine does not guess.

### Optional AI explanation

If `ANTHROPIC_API_KEY` is set (and `pip install -e "apps/api[ai]"`),
`GET /api/incidents/{id}/analysis?ai=true` attaches a short AI-generated
summary. The prompt contains only the structured analysis and its evidence,
forbids unsupported conclusions, and the response is validated (length,
on-category) before being stored; it is always labeled as AI-generated in the
UI and report, and everything falls back to the deterministic explanation
without a key.

## ROS 2 integration path

ROS 2 is not required. The path from a live robot or bag file:

1. **rosbag2 (MCAP) ingestion — implemented.** Upload a `.mcap` bag to
   `POST /api/incidents/upload` with a small metadata JSON (`id`,
   `robot_id`, optional overrides); the adapter decodes `/odom`, `/cmd_vel`,
   `/scan`, `/amcl_pose`, and `/navigate_to_pose/_action/status` with
   pure-Python `mcap-ros2-support`, derives the outcome from the terminal
   goal status, and runs the normal validate→persist→analyze pipeline.
   `make demo-bag` writes a deterministic sample bag and prints the upload
   command.
2. **Adapter interface** — [robotics/adapters/README.md](robotics/adapters/README.md)
   documents `IncidentAdapter`; new formats plug into the same pipeline.
3. **Topic mapping** — pure, ROS-free conversion helpers live in
   [ros2_mapping.py](apps/api/blackbox_api/ros2_mapping.py) (re-exported for
   ROS environments via `robotics/adapters/ros2_topic_mapping.py`).
4. **Live recorder** — [robotics/ros2/blackbox_recorder.py](robotics/ros2/blackbox_recorder.py)
   is an example `rclpy` node that buffers canonical samples and POSTs an
   incident when a Nav2 goal aborts.

## Testing

```bash
make test        # backend (pytest) + frontend (vitest)
make lint        # ruff, mypy --strict, eslint, tsc --noEmit
make build       # next build
make demo        # in one shell…
make smoke       # …then the end-to-end smoke test in another
```

Backend tests cover schema validation, event ordering, both ingestion
adapters, invalid-upload errors, all four diagnoses (plus determinism and
distinctness), API response shapes/filters, and Pydantic⇄TypeScript schema
sync. Frontend tests cover the replay store (tick, pause-at-failure, speed,
clamping), overview rendering/filters/error/empty states, timeline selection
and category filters, evidence timestamp navigation, replay controls, the
event inspector, and report rendering.

## Limitations

- SQLite + `create_all` initialization — right for a local MVP; a real
  deployment would want Postgres and migrations.
- Telemetry is stored row-per-sample; fine at demo scale, but long incidents
  would warrant chunked storage.
- rosbag2 ingestion supports the MCAP storage format and the five core
  Nav2 topics; `/behavior_tree_log` (recovery events), `/diagnostics`, and
  the sqlite3 (`.db3`) storage plugin are not handled yet, and it has been
  validated against synthetic bags, not hardware recordings. The live
  recorder node is an example, untested against real hardware.
- The AI layer supports the Anthropic API only (an OpenAI client would be a
  small addition to `blackbox_api/ai/explain.py`).
- No authentication — BlackBox assumes a trusted network.
- `docker compose` config is provided but was not runnable in this
  development environment (no Docker daemon); validate on a machine with
  Docker before relying on it.

## Roadmap

- rosbag2 adapter coverage: `/behavior_tree_log`, `/diagnostics`, `.db3`
  storage, goal-distance derivation
- Cross-incident analytics: recurring blockage locations, failure trends per
  software version
- Rule plug-ins with per-facility thresholds
- Live streaming ingestion (websocket) with rolling pre-failure buffers
- Incident diffing: compare a failure against a known-good run

## Contributing

- `make setup && make test && make lint` must pass before a PR.
- The canonical schema changes in three places together: the Pydantic model,
  the TypeScript mirror, and `make schema` for the JSON export —
  `test_schema_sync.py` will catch drift.
- New failure modes should come as a rule (features + weighted conditions +
  evidence) plus a deterministic sample incident that triggers it and tests
  proving the diagnosis.
- Keep adapters pure (bytes → `Incident`); persistence and analysis stay in
  the ingestion service.
