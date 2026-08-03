# Sample external incidents

Worked examples of the upload formats BlackBox accepts.

## Normalized CSV events

`normalized-events.example.csv` shows the CSV event format. CSV files carry
only events; incident-level metadata is supplied alongside the upload as a
JSON form field:

```bash
curl -X POST http://localhost:8000/api/incidents/upload \
  -F "file=@robotics/sample-incidents/normalized-events.example.csv" \
  -F 'metadata={
        "id": "INC-CSV-DEMO-001",
        "robot_id": "W-042",
        "robot_model": "Fetchbot AMR-600",
        "facility": "Warehouse 3 — Fremont",
        "task_name": "Move pallet to staging",
        "task_goal": "Deliver pallet to the staging area",
        "start_time": "2026-07-20T08:00:00Z",
        "end_time": "2026-07-20T08:01:30Z",
        "outcome": "timed_out",
        "severity": "error",
        "software_version": "nav-stack 2.14.1",
        "map_version": "warehouse3-2026.07.12",
        "environment": "Indoor warehouse",
        "summary": "CSV-imported navigation timeout"
      }'
```

Required CSV columns: `timestamp`, `event_type`, `subsystem`, `severity`,
`message`. Optional: `payload` (JSON object), `correlation_id`,
`evidence_tags` (semicolon-separated).

## Full JSON incidents

The four seeded incidents in `packages/sample-data/incidents/` are complete
JSON examples (events **and** telemetry). Any file with the same shape can be
uploaded:

```bash
curl -X POST http://localhost:8000/api/incidents/upload \
  -F "file=@packages/sample-data/incidents/INC-2026-0728-001.json"
```
