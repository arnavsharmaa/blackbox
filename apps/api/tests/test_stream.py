from __future__ import annotations

import pytest

from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.ingestion.stream import RobotStream, StreamError

BASE_T = 1_785_000_000.0  # an arbitrary unix timestamp


def _stream(window_s: float = 600.0) -> RobotStream:
    stream = RobotStream(robot_id="W-500", window_s=window_s)
    stream.update_meta({
        "robot_model": "Fetchbot AMR-600",
        "facility": "Warehouse 9",
        "task_name": "Streamed delivery",
        "task_goal": "Reach dock 4",
        "software_version": "nav-stack 2.14.1",
        "map_version": "w9-2026.08",
        "environment": "Indoor warehouse",
        "ignored_field": "dropped",
    })
    return stream


def _event(t: float, event_type: str, **extra: object) -> dict[str, object]:
    return {
        "t": BASE_T + t,
        "event_type": event_type,
        "subsystem": "task_manager",
        "message": f"{event_type} at {t}",
        **extra,
    }


def test_terminal_event_is_detected() -> None:
    stream = _stream()
    assert stream.add_event(_event(0.0, "task_started")) is None
    assert stream.add_event(_event(5.0, "task_failed")) == "task_failed"


def test_old_entries_fall_out_of_the_window() -> None:
    stream = _stream(window_s=60.0)
    stream.add_event(_event(0.0, "task_started"))
    stream.add_sample(
        {"t": BASE_T, "channel": "pos_x", "value": 1.0, "unit": "m"}
    )
    # Two minutes later, the first entries are outside the window.
    stream.add_event(_event(120.0, "task_failed", severity="critical"))
    incident = stream.cut(terminal_event="task_failed")
    assert len(incident.events) == 1
    assert incident.telemetry == []


def test_cut_builds_a_valid_diagnosable_incident() -> None:
    stream = _stream()
    stream.add_event(_event(0.0, "task_started"))
    for i in range(30):
        t = 1.0 + i
        stream.add_sample({
            "t": BASE_T + t, "channel": "obstacle_distance",
            "value": 0.4, "unit": "m",
        })
        stream.add_sample({
            "t": BASE_T + t, "channel": "linear_velocity",
            "value": 0.0, "unit": "m/s",
        })
        stream.add_event({
            "t": BASE_T + t, "event_type": "velocity_command",
            "subsystem": "controller", "message": "cmd_vel 0.0",
            "payload": {"linear": 0.0, "angular": 0.0},
        })
    stream.add_event(_event(31.0, "task_failed", severity="critical"))

    incident = stream.cut(terminal_event="task_failed")
    assert incident.robot_id == "W-500"
    assert incident.outcome.value == "failed"
    assert incident.severity.value == "critical"
    assert incident.id.startswith("INC-STREAM-W-500-")
    # Sample times are re-based to seconds from the window start.
    first = incident.telemetry[0].samples[0]
    assert first.t == pytest.approx(1.0)
    # The buffered window is analyzable by the normal engine.
    analysis = analyze_incident(incident)
    assert analysis.confidence >= 0.0

    # The buffer resets after a cut.
    with pytest.raises(StreamError, match="no buffered events"):
        stream.cut()


def test_cut_overrides_win() -> None:
    stream = _stream()
    stream.add_event(_event(0.0, "warning_raised", severity="warning"))
    incident = stream.cut(
        incident_id="INC-NEAR-MISS-1",
        outcome="success",
        severity="warning",
        summary="Operator flagged a near-miss.",
    )
    assert incident.id == "INC-NEAR-MISS-1"
    assert incident.outcome.value == "success"
    assert incident.summary == "Operator flagged a near-miss."


def test_bad_messages_are_rejected_up_front() -> None:
    stream = _stream()
    with pytest.raises(StreamError, match="unix timestamp"):
        stream.add_event({"event_type": "task_started"})
    with pytest.raises(StreamError, match="unknown event_type"):
        stream.add_event(_event(0.0, "robot_exploded"))
    with pytest.raises(StreamError, match="missing 'message'"):
        stream.add_event({
            "t": BASE_T, "event_type": "task_started",
            "subsystem": "task_manager",
        })
    with pytest.raises(StreamError, match="unknown telemetry channel"):
        stream.add_sample({"t": BASE_T, "channel": "vibes", "value": 1.0})
    with pytest.raises(StreamError, match="missing 'value'"):
        stream.add_sample({"t": BASE_T, "channel": "pos_x"})


def test_meta_only_accepts_known_fields() -> None:
    stream = _stream()
    assert "ignored_field" not in stream.meta
    assert stream.meta["facility"] == "Warehouse 9"
