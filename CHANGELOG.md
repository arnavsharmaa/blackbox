# Changelog

Notable changes to BlackBox. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions track
the API/package version in `apps/api/pyproject.toml`.

## [Unreleased]

### Added

- Incident triage: every incident moves through open → investigating →
  resolved from the incident header, with an overview filter and
  badges; existing databases come up all-open.
- Incident notes: a free-text investigation scratchpad per incident
  (API + panel on the incident page), carried through `blackbox show`,
  backup, and restore; cited in the incident report and manageable
  from the terminal with `blackbox notes`.

- Overview: free-text search, pagination, shareable filter URLs,
  facility filter, CSV export link, drag-and-drop upload.
- Robots roster (`/robots`) with per-robot last-incident dates; robot
  ids link to their filtered history everywhere.
- Fleet analytics date-range picker and a staged README screenshot.
- Incident page: canonical-JSON download; branded 404/error pages.
- Reports and generated GitHub issues cite prior occurrences of the
  failure signature.
- CLI: `diff`, `doctor`, `watch`, `backup`/`restore`; `make
  demo-stream`.
- Optional per-client write rate limiting
  (`BLACKBOX_RATE_LIMIT_PER_MINUTE`).
- `/health` reports app version and database migration revision.
- A worked example plug-in rule (`examples/rules/recovery_churn.py`),
  exercised by the test suite.
- Tag-driven release workflow (CHANGELOG notes + spec/schema assets).
- Docs: a complete configuration reference (drift-guarded by a test)
  and a production deployment guide.

### Changed

- Playwright upgraded to 1.65 (Ubuntu 26.04 runners supported); failed
  e2e runs keep replayable traces as CI artifacts.

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
