"""Normalized CSV event-stream adapter.

Expected columns (header row required):
    timestamp, event_type, subsystem, severity, message,
    payload (optional, JSON object), correlation_id (optional),
    evidence_tags (optional, semicolon-separated)

Incident-level metadata (id, robot_id, times, ...) does not exist in the CSV
and must be supplied via ``metadata``. See
robotics/sample-incidents/normalized-events.example.csv for a worked example.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from pydantic import ValidationError

from blackbox_api.ingestion.base import IncidentAdapter, IngestError
from blackbox_api.ingestion.json_adapter import format_validation_error
from blackbox_api.schemas import Incident

REQUIRED_COLUMNS = {"timestamp", "event_type", "subsystem", "severity", "message"}


class CsvIncidentAdapter(IncidentAdapter):
    name = "csv"
    extensions = (".csv",)

    def parse(self, raw: bytes, *, metadata: dict[str, Any] | None = None) -> Incident:
        if not metadata:
            raise IngestError(
                "CSV uploads require an incident metadata JSON part with "
                "fields such as id, robot_id, start_time and end_time"
            )
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise IngestError("CSV file is not valid UTF-8") from exc

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise IngestError("CSV file is empty (missing header row)")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise IngestError(
                f"CSV header is missing required columns: {', '.join(sorted(missing))}"
            )

        events: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for line_no, row in enumerate(reader, start=2):
            payload_text = (row.get("payload") or "").strip()
            payload: dict[str, Any] = {}
            if payload_text:
                try:
                    parsed = json.loads(payload_text)
                    if not isinstance(parsed, dict):
                        raise ValueError("payload must be a JSON object")
                    payload = parsed
                except (json.JSONDecodeError, ValueError) as exc:
                    errors.append(
                        {
                            "field": f"row {line_no}.payload",
                            "error": f"invalid payload JSON: {exc}",
                            "input_preview": payload_text[:120],
                        }
                    )
                    continue
            tags_text = (row.get("evidence_tags") or "").strip()
            events.append(
                {
                    "timestamp": (row.get("timestamp") or "").strip(),
                    "event_type": (row.get("event_type") or "").strip(),
                    "subsystem": (row.get("subsystem") or "").strip(),
                    "severity": (row.get("severity") or "info").strip() or "info",
                    "message": (row.get("message") or "").strip(),
                    "payload": payload,
                    "correlation_id": (row.get("correlation_id") or "").strip() or None,
                    "evidence_tags": [
                        t.strip() for t in tags_text.split(";") if t.strip()
                    ],
                }
            )
        if errors:
            raise IngestError("CSV rows failed validation", details=errors)
        if not events:
            raise IngestError("CSV file contains a header but no event rows")

        data = {**metadata, "events": events}
        data.setdefault("telemetry", [])
        try:
            return Incident.model_validate(data)
        except ValidationError as exc:
            raise IngestError(
                "incident assembled from CSV failed schema validation",
                details=format_validation_error(exc),
            ) from exc
