# Contributing to BlackBox

Thanks for helping make robot failures explainable. Contributions of every
size are welcome — the single most valuable one is a **real failure bag**
(see below).

## The fastest way to help: share a failure bag

BlackBox's ingestion and rules have been validated against deterministic
synthetic data. What the project needs most is contact with reality:

1. Record a failed Nav2 task with `ros2 bag record -s mcap` (topics:
   `/odom`, `/cmd_vel`, `/scan`, `/amcl_pose`, `/plan`,
   `/navigate_to_pose/_action/status`, `/behavior_tree_log`,
   `/diagnostics` — any subset works).
2. Upload it on the **Upload** page (or `POST /api/incidents/upload`).
3. Open a [bag validation report](https://github.com/arnavsharmaa/blackbox/issues/new?template=bag-validation.md)
   telling us what the diagnosis got right or wrong.

See [docs/hardware-validation.md](docs/hardware-validation.md) for a
walkthrough that needs no hardware (Gazebo + TurtleBot3).

## Development setup

```bash
make setup   # venv + backend deps + npm install
make seed    # deterministic sample incidents
make dev     # API on :8000, web on :3000
```

`make test && make lint` must pass before a PR. That runs pytest, vitest,
ruff, mypy --strict, eslint, and tsc. `make e2e` runs the Playwright suite
against a running stack.

## Ground rules

- **The diagnosis loop stays deterministic.** No LLM may influence
  `failure_category`, `confidence`, or evidence. AI may only summarize an
  already-computed analysis, clearly labeled.
- **The canonical schema changes in three places together**: the Pydantic
  model, the TypeScript mirror, and `make schema` for the JSON export.
  `test_schema_sync.py` catches drift.
- **New failure modes arrive as a rule**: derived features + weighted
  conditions + evidence anchors, plus a deterministic sample incident that
  triggers it and tests proving the diagnosis. Rules can also live outside
  the repo as [`BLACKBOX_EXTRA_RULES` plug-ins](apps/api/blackbox_api/analysis/plugins.py).
- **Adapters stay pure** (bytes → `Incident`); persistence and analysis
  belong to the ingestion service.
- Thresholds are configuration (`BLACKBOX_RULE_*`), not magic numbers.

## Commit style

Present-tense, imperative subject lines ("Add sensor-dropout rule", not
"Added…"). Keep each commit self-contained: code + tests + docs together.

## License

By contributing you agree your contributions are licensed under the
[MIT License](LICENSE).
