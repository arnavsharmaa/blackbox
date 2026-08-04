from __future__ import annotations

import json

import pytest

from blackbox_api.ingestion.base import IngestError
from blackbox_api.ingestion.csv_adapter import CsvIncidentAdapter
from blackbox_api.ingestion.json_adapter import JsonIncidentAdapter
from blackbox_api.ingestion.service import adapter_for_filename

CSV_METADATA = {
    "id": "INC-CSV-001",
    "robot_id": "W-500",
    "robot_model": "TestBot",
    "facility": "Test Facility",
    "task_name": "CSV import task",
    "task_goal": "Validate the CSV adapter",
    "start_time": "2026-07-01T10:00:00Z",
    "end_time": "2026-07-01T10:01:00Z",
    "outcome": "failed",
    "severity": "error",
    "software_version": "1.0.0",
    "map_version": "map-1",
    "environment": "test",
    "summary": "CSV ingested incident",
}

CSV_BODY = (
    "timestamp,event_type,subsystem,severity,message,payload,correlation_id,"
    "evidence_tags\n"
    '2026-07-01T10:00:00Z,task_started,task_manager,info,started,'
    '"{""task"": ""csv""}",T-1,\n'
    "2026-07-01T10:00:30Z,warning_raised,planner,warning,plan degraded,,T-1,"
    "planner;degraded\n"
    "2026-07-01T10:00:55Z,task_failed,task_manager,critical,failed,,T-1,\n"
)


def test_adapter_selection() -> None:
    assert adapter_for_filename("incident.json").name == "json"
    assert adapter_for_filename("events.CSV").name == "csv"
    assert adapter_for_filename("rosbag2_0.mcap").name == "rosbag2"
    with pytest.raises(IngestError, match="unsupported file type"):
        adapter_for_filename("bag.db3")


def test_json_adapter_roundtrip(sample_incidents: dict[str, dict]) -> None:
    raw = json.dumps(sample_incidents["obstacle"]).encode()
    incident = JsonIncidentAdapter().parse(raw)
    assert incident.id == "INC-2026-0728-001"
    assert incident.robot_id == "W-104"


def test_json_adapter_rejects_malformed_json() -> None:
    with pytest.raises(IngestError, match="not valid JSON"):
        JsonIncidentAdapter().parse(b"{not json")


def test_json_adapter_reports_field_errors() -> None:
    with pytest.raises(IngestError) as exc:
        JsonIncidentAdapter().parse(json.dumps({"id": "X"}).encode())
    fields = {d["field"] for d in exc.value.details}
    assert "robot_id" in fields
    assert "events" in fields


def test_csv_adapter_parses_events() -> None:
    incident = CsvIncidentAdapter().parse(
        CSV_BODY.encode(), metadata=CSV_METADATA
    )
    assert len(incident.events) == 3
    assert incident.events[0].payload == {"task": "csv"}
    assert incident.events[1].evidence_tags == ["planner", "degraded"]


def test_csv_adapter_requires_metadata() -> None:
    with pytest.raises(IngestError, match="metadata"):
        CsvIncidentAdapter().parse(CSV_BODY.encode())


def test_csv_adapter_rejects_missing_columns() -> None:
    with pytest.raises(IngestError, match="missing required columns"):
        CsvIncidentAdapter().parse(
            b"timestamp,message\n2026-07-01T10:00:00Z,hi\n",
            metadata=CSV_METADATA,
        )


def test_csv_adapter_rejects_bad_payload_json() -> None:
    body = (
        "timestamp,event_type,subsystem,severity,message,payload\n"
        "2026-07-01T10:00:00Z,task_started,task_manager,info,started,{bad}\n"
    )
    with pytest.raises(IngestError, match="rows failed validation"):
        CsvIncidentAdapter().parse(body.encode(), metadata=CSV_METADATA)


def test_csv_adapter_rejects_empty_file() -> None:
    with pytest.raises(IngestError, match="empty"):
        CsvIncidentAdapter().parse(b"", metadata=CSV_METADATA)
