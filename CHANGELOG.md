# Changelog

Notable changes to BlackBox. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions track
the API/package version in `apps/api/pyproject.toml`.

## [0.2.0] — 2026-10-19

### Added

- **Recurring-failure intelligence**: failure signatures (the same task
  diagnosed with the same category more than once) in fleet analytics, a
  "this happened before" panel on the incident page, prior-occurrence
  citations in reports and generated GitHub issues, and occurrence
  numbers in webhook alerts.
- **Live streaming ingestion**: robots stream events/telemetry to
  `ws://…/api/stream/{robot_id}`; a rolling pre-failure window
  (`BLACKBOX_STREAM_WINDOW_S`) is cut into an analyzed incident on
  terminal events or an explicit near-miss cut. The example ROS 2
  recorder node streams instead of buffering client-side.
- **Multi-tenancy & auth**: full (`BLACKBOX_API_TOKENS`), read-only
  (`BLACKBOX_READONLY_TOKENS`), and facility-scoped
  (`BLACKBOX_FACILITY_TOKENS`) API tokens; facility isolation across
  every read, write, stream, analytics, and export path.
- **Diagnosis feedback & calibration**: engineers confirm or correct
  diagnoses; analytics reports measured precision per category and the
  incident page shows it beside the engine's confidence.
- **Incident diffing**: compare a failure against a known-good baseline
  run with per-channel first-divergence detection; successful baseline
  sample incident included.
- **`blackbox` CLI**: list, show, upload, replay (WebSocket robot
  simulator), watch, backup/restore, prune.
- **Operations**: Slack-compatible webhook notifications
  (`BLACKBOX_WEBHOOK_URL`), retention pruning
  (`DELETE /api/incidents?before=…`), CSV export, configurable upload
  cap, enriched `/health` (version + migration revision).
- **Web app**: fleet analytics with date-range window, robots roster,
  shareable filter URLs, free-text search, pagination, drag-and-drop
  upload, replay deep links (`?t=`), facility filter.
- **Postgres support**: Alembic migrations (legacy databases adopted in
  place), `postgres` extra, docker-compose override, and a CI job
  running the full backend suite against Postgres.
- **Chunked telemetry storage**: one row per channel instead of one per
  sample; migration converts existing data in place.

### Changed

- Database initialization runs Alembic migrations instead of
  `create_all`; datetime columns are timezone-aware (timestamptz on
  Postgres).
- The incident list caps at one page server-side and paginates in the
  UI instead of silently truncating.

## [0.1.0] — 2026-08-03

Initial release: canonical incident schema (Pydantic ⇄ TypeScript),
JSON/CSV/rosbag2-MCAP ingestion with field-level errors, deterministic
four-rule analysis engine with evidence and configurable thresholds
(`BLACKBOX_RULE_*`) and rule plug-ins (`BLACKBOX_EXTRA_RULES`),
state-driven replay UI (timeline, synced telemetry, 2D path map,
evidence panel), incident reports and GitHub issue generation, fleet
analytics with blockage hotspots, optional labeled AI summaries, Docker
Compose, and CI (backend, frontend, Docker smoke, Playwright e2e).
