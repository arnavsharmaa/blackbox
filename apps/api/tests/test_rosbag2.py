from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from ros2_bag_builder import build_blocked_run_bag

from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.ingestion.base import IngestError
from blackbox_api.ingestion.rosbag2_adapter import Rosbag2Adapter
from blackbox_api.ingestion.service import adapter_for_filename
from blackbox_api.schemas import FailureCategory

METADATA = {
    "id": "INC-BAG-001",
    "robot_id": "W-104",
    "facility": "Warehouse 3 — Fremont",
    "task_name": "Deliver pallet (bag capture)",
}


@pytest.fixture(scope="module")
def bag_bytes() -> bytes:
    return build_blocked_run_bag()


def test_adapter_selected_for_mcap() -> None:
    assert adapter_for_filename("run_0.mcap").name == "rosbag2"


def test_bag_parses_to_canonical_incident(bag_bytes: bytes) -> None:
    incident = Rosbag2Adapter().parse(bag_bytes, metadata=METADATA)

    assert incident.id == "INC-BAG-001"
    assert incident.robot_id == "W-104"
    assert incident.outcome.value == "failed"  # STATUS_ABORTED → failed
    assert incident.facility == "Warehouse 3 — Fremont"  # override applied
    assert incident.robot_model == "unknown"  # default applied

    channels = {series.channel.value for series in incident.telemetry}
    assert {
        "pos_x", "pos_y", "heading", "linear_velocity", "angular_velocity",
        "obstacle_distance", "localization_confidence", "planner_state",
        "recovery_count",
    } <= channels

    event_types = {event.event_type.value for event in incident.events}
    assert {
        "task_started", "nav_goal_issued", "velocity_command",
        "pose_updated", "task_failed", "recovery_started",
        "recovery_completed", "planner_state_changed",
    } <= event_types

    # The behavior-tree log yields three failed recoveries and a replan.
    recoveries = [
        e for e in incident.events if e.event_type.value == "recovery_started"
    ]
    assert [e.payload["behavior"] for e in recoveries] == [
        "Spin", "BackUp", "Wait",
    ]
    states = next(
        s for s in incident.telemetry if s.channel.value == "planner_state"
    )
    assert [sample.value for sample in states.samples] == [
        "planning", "executing", "replanning",
    ]

    # Obstacle clearance drops to 0.5 m once the obstacle appears at t=12 s.
    obstacle = next(
        s for s in incident.telemetry if s.channel.value == "obstacle_distance"
    )
    late = [
        float(sample.value) for sample in obstacle.samples if sample.t > 13.0
    ]
    assert late and all(value < 0.6 for value in late)


def test_bag_incident_gets_obstacle_diagnosis(bag_bytes: bytes) -> None:
    incident = Rosbag2Adapter().parse(bag_bytes, metadata=METADATA)
    analysis = analyze_incident(incident)
    assert analysis.failure_category == FailureCategory.PERSISTENT_OBSTACLE
    # Recovery evidence from the behavior-tree log lifts confidence well
    # above what odometry/scan/cmd_vel alone can support.
    assert analysis.confidence >= 0.75
    summaries = " | ".join(item.summary for item in analysis.evidence)
    assert "zero-velocity commands" in summaries
    assert "3 recovery behaviors were attempted" in summaries
    assert "Spin, BackUp, Wait" in summaries


def test_bag_requires_metadata(bag_bytes: bytes) -> None:
    with pytest.raises(IngestError, match="metadata"):
        Rosbag2Adapter().parse(bag_bytes)
    with pytest.raises(IngestError, match="robot_id"):
        Rosbag2Adapter().parse(bag_bytes, metadata={"id": "X"})


def test_garbage_bytes_rejected() -> None:
    with pytest.raises(IngestError, match="not a readable MCAP bag"):
        Rosbag2Adapter().parse(b"not an mcap file", metadata=METADATA)


def test_metadata_start_time_rebases_clock(bag_bytes: bytes) -> None:
    incident = Rosbag2Adapter().parse(
        bag_bytes,
        metadata={**METADATA, "start_time": "2026-08-01T12:00:00Z"},
    )
    assert incident.start_time.isoformat().startswith("2026-08-01T12:00:00")


def test_upload_endpoint_accepts_mcap(
    client: TestClient, bag_bytes: bytes
) -> None:
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("run_0.mcap", bag_bytes, "application/octet-stream")},
        data={"metadata": json.dumps(METADATA)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["incident_id"] == "INC-BAG-001"
    assert body["failure_category"] == "persistent_obstacle"

    detail = client.get("/api/incidents/INC-BAG-001").json()
    assert detail["analysis"]["failure_category"] == "persistent_obstacle"
