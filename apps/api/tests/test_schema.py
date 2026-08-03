from __future__ import annotations

import pytest
from pydantic import ValidationError

from blackbox_api.schemas import Incident


def _minimal(**overrides) -> dict:
    base = {
        "id": "INC-TEST-001",
        "robot_id": "W-001",
        "robot_model": "TestBot",
        "facility": "Test Facility",
        "task_name": "Test task",
        "task_goal": "Reach the goal",
        "start_time": "2026-07-01T10:00:00Z",
        "end_time": "2026-07-01T10:01:00Z",
        "outcome": "failed",
        "severity": "error",
        "software_version": "1.0.0",
        "map_version": "map-1",
        "environment": "test",
        "summary": "A test incident",
        "events": [
            {
                "timestamp": "2026-07-01T10:00:00Z",
                "event_type": "task_started",
                "subsystem": "task_manager",
                "severity": "info",
                "message": "started",
            }
        ],
        "telemetry": [],
    }
    base.update(overrides)
    return base


def test_valid_minimal_incident_parses() -> None:
    incident = Incident.model_validate(_minimal())
    assert incident.id == "INC-TEST-001"
    assert incident.duration_s == 60.0


def test_sample_incidents_validate(sample_incidents: dict[str, dict]) -> None:
    for name, raw in sample_incidents.items():
        incident = Incident.model_validate(raw)
        assert incident.events, name
        assert incident.telemetry, name


def test_missing_required_field_rejected() -> None:
    data = _minimal()
    del data["robot_id"]
    with pytest.raises(ValidationError) as exc:
        Incident.model_validate(data)
    assert "robot_id" in str(exc.value)


def test_bad_enum_rejected() -> None:
    with pytest.raises(ValidationError):
        Incident.model_validate(_minimal(outcome="exploded"))


def test_end_before_start_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Incident.model_validate(_minimal(end_time="2026-07-01T09:00:00Z"))
    assert "end_time" in str(exc.value)


def test_event_outside_window_rejected() -> None:
    data = _minimal()
    data["events"][0]["timestamp"] = "2026-07-01T12:00:00Z"
    with pytest.raises(ValidationError):
        Incident.model_validate(data)


def test_events_sorted_canonically() -> None:
    data = _minimal()
    data["events"] = [
        {
            "timestamp": "2026-07-01T10:00:30Z",
            "event_type": "task_failed",
            "subsystem": "task_manager",
            "severity": "error",
            "message": "failed",
        },
        {
            "timestamp": "2026-07-01T10:00:00Z",
            "event_type": "task_started",
            "subsystem": "task_manager",
            "severity": "info",
            "message": "started",
        },
    ]
    incident = Incident.model_validate(data)
    timestamps = [e.timestamp for e in incident.events]
    assert timestamps == sorted(timestamps)
    assert incident.events[0].event_type.value == "task_started"


def test_string_channel_rejects_numeric_samples() -> None:
    data = _minimal(
        telemetry=[
            {
                "channel": "planner_state",
                "unit": "",
                "samples": [{"t": 0.0, "value": 1.5}],
            }
        ]
    )
    with pytest.raises(ValidationError) as exc:
        Incident.model_validate(data)
    assert "planner_state" in str(exc.value)


def test_numeric_channel_rejects_string_samples() -> None:
    data = _minimal(
        telemetry=[
            {
                "channel": "linear_velocity",
                "unit": "m/s",
                "samples": [{"t": 0.0, "value": "fast"}],
            }
        ]
    )
    with pytest.raises(ValidationError):
        Incident.model_validate(data)


def test_unordered_telemetry_rejected() -> None:
    data = _minimal(
        telemetry=[
            {
                "channel": "linear_velocity",
                "unit": "m/s",
                "samples": [
                    {"t": 5.0, "value": 0.5},
                    {"t": 1.0, "value": 0.2},
                ],
            }
        ]
    )
    with pytest.raises(ValidationError):
        Incident.model_validate(data)


def test_duplicate_channel_rejected() -> None:
    channel = {
        "channel": "linear_velocity",
        "unit": "m/s",
        "samples": [{"t": 0.0, "value": 0.1}],
    }
    with pytest.raises(ValidationError):
        Incident.model_validate(_minimal(telemetry=[channel, dict(channel)]))
