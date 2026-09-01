from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["incidents"] == 0
    assert "engine_version" in body


def test_list_incidents_shape_and_pagination(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/incidents", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    item = body["items"][0]
    for key in (
        "id", "robot_id", "severity", "outcome", "duration_s",
        "failure_category", "confidence", "event_count",
    ):
        assert key in item
    # Sorted newest first.
    starts = [i["start_time"] for i in body["items"]]
    assert starts == sorted(starts, reverse=True)


def test_list_incidents_filters(seeded_client: TestClient) -> None:
    by_robot = seeded_client.get(
        "/api/incidents", params={"robot_id": "W-104"}
    ).json()
    # W-104 has the primary failure and its successful baseline run.
    assert by_robot["total"] == 2
    assert {i["id"] for i in by_robot["items"]} == {
        "INC-2026-0728-001", "INC-2026-0721-BASE",
    }

    by_severity = seeded_client.get(
        "/api/incidents", params={"severity": "critical"}
    ).json()
    assert {i["severity"] for i in by_severity["items"]} == {"critical"}

    by_category = seeded_client.get(
        "/api/incidents", params={"failure_category": "sensor_dropout"}
    ).json()
    assert by_category["total"] == 1
    assert by_category["items"][0]["id"] == "INC-2026-0731-004"

    by_outcome = seeded_client.get(
        "/api/incidents", params={"outcome": "aborted"}
    ).json()
    assert by_outcome["total"] == 1


def test_get_incident_detail(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/incidents/INC-2026-0728-001")
    assert response.status_code == 200
    body = response.json()
    assert body["incident"]["robot_id"] == "W-104"
    assert len(body["incident"]["events"]) == 91
    channels = {s["channel"] for s in body["incident"]["telemetry"]}
    assert {"pos_x", "pos_y", "obstacle_distance", "planner_state"} <= channels
    assert body["analysis"]["failure_category"] == "persistent_obstacle"


def test_get_incident_404(client: TestClient) -> None:
    response = client.get("/api/incidents/NOPE")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_events_endpoint_ordering_and_filters(seeded_client: TestClient) -> None:
    events = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/events"
    ).json()
    timestamps = [
        datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        for e in events
    ]
    assert timestamps == sorted(timestamps)

    warnings = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/events",
        params={"severity": "warning"},
    ).json()
    assert warnings
    assert all(e["severity"] == "warning" for e in warnings)

    recoveries = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/events",
        params={"event_type": "recovery_started"},
    ).json()
    assert len(recoveries) == 3


def test_telemetry_endpoint(seeded_client: TestClient) -> None:
    series = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/telemetry"
    ).json()
    channels = {s["channel"] for s in series}
    assert "linear_velocity" in channels

    only_obstacle = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/telemetry",
        params={"channel": "obstacle_distance"},
    ).json()
    assert len(only_obstacle) == 1
    assert only_obstacle[0]["samples"][0]["t"] == 0.0


def test_analysis_endpoint(seeded_client: TestClient) -> None:
    body = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/analysis"
    ).json()
    assert body["failure_category"] == "persistent_obstacle"
    assert 0 <= body["confidence"] <= 1
    assert body["evidence"]
    assert body["recommended_actions"]
    assert body["ai_explanation"] is None


def test_reanalyze_endpoint(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        "/api/incidents/INC-2026-0730-003/reanalyze"
    )
    assert response.status_code == 200
    assert (
        response.json()["analysis"]["failure_category"]
        == "controller_oscillation"
    )


def test_report_endpoint(seeded_client: TestClient) -> None:
    report = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/report"
    ).json()
    assert report["incident"]["id"] == "INC-2026-0728-001"
    assert report["root_cause"]["category"] == "persistent_obstacle"
    assert report["evidence"]
    assert report["timeline"]
    assert report["telemetry_summary"]
    assert "# Incident Report" in report["markdown"]
    assert "## Reproduction notes" in report["markdown"]


def test_github_issue_endpoint(seeded_client: TestClient) -> None:
    issue = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/github-issue",
        params={"repo": "acme/warehouse-robots"},
    ).json()
    assert "W-104" in issue["title"]
    assert "## Steps to reproduce" in issue["body"]
    assert "## Evidence" in issue["body"]
    assert issue["issue_url"].startswith(
        "https://github.com/acme/warehouse-robots/issues/new?"
    )
    no_repo = seeded_client.get(
        "/api/incidents/INC-2026-0728-001/github-issue"
    ).json()
    assert no_repo["issue_url"] is None


def test_upload_json_incident(client: TestClient, sample_incidents) -> None:
    raw = json.dumps(sample_incidents["obstacle"]).encode()
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("incident.json", raw, "application/json")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["incident_id"] == "INC-2026-0728-001"
    assert body["failure_category"] == "persistent_obstacle"


def test_upload_invalid_json_gives_useful_error(client: TestClient) -> None:
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("bad.json", b"{oops", "application/json")},
    )
    assert response.status_code == 422
    assert "not valid JSON" in response.json()["detail"]["message"]


def test_upload_schema_violation_lists_fields(client: TestClient) -> None:
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("bad.json", json.dumps({"id": "X"}).encode(),
                        "application/json")},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "incident failed schema validation"
    assert any(e["field"] == "robot_id" for e in detail["errors"])


def test_prune_removes_incidents_before_cutoff(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.delete(
        "/api/incidents", params={"before": "2026-07-28T00:00:00Z"}
    )
    assert response.status_code == 200
    body = response.json()
    # Only the successful baseline run predates the failures.
    assert body == {"deleted": 1, "incident_ids": ["INC-2026-0721-BASE"]}
    assert seeded_client.get("/api/incidents").json()["total"] == 4

    # Pruning again with the same cutoff is a no-op.
    again = seeded_client.delete(
        "/api/incidents", params={"before": "2026-07-28T00:00:00Z"}
    ).json()
    assert again["deleted"] == 0


def test_prune_requires_a_cutoff(seeded_client: TestClient) -> None:
    assert seeded_client.delete("/api/incidents").status_code == 422


def test_upload_size_limit_is_configurable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from blackbox_api.config import get_settings

    monkeypatch.setenv("BLACKBOX_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/incidents/upload",
            files={
                "file": (
                    "big.json",
                    b"x" * (1024 * 1024 + 1),
                    "application/json",
                )
            },
        )
        assert response.status_code == 422
        assert "exceeds the 1 MB limit" in response.json()["detail"]["message"]
    finally:
        get_settings.cache_clear()


def test_upload_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("data.parquet", b"x", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "unsupported file type" in response.json()["detail"]["message"]


def test_upload_csv_with_metadata(client: TestClient) -> None:
    csv_body = (
        "timestamp,event_type,subsystem,severity,message\n"
        "2026-07-01T10:00:00Z,task_started,task_manager,info,started\n"
        "2026-07-01T10:00:55Z,task_failed,task_manager,error,failed\n"
    )
    metadata = {
        "id": "INC-CSV-API-001",
        "robot_id": "W-777",
        "robot_model": "TestBot",
        "facility": "Test Facility",
        "task_name": "CSV upload",
        "task_goal": "Verify CSV upload endpoint",
        "start_time": "2026-07-01T10:00:00Z",
        "end_time": "2026-07-01T10:01:00Z",
        "outcome": "failed",
        "severity": "error",
        "software_version": "1.0.0",
        "map_version": "map-1",
        "environment": "test",
        "summary": "CSV upload test",
    }
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("events.csv", csv_body.encode(), "text/csv")},
        data={"metadata": json.dumps(metadata)},
    )
    assert response.status_code == 201
    assert response.json()["event_count"] == 2


def test_upload_csv_without_metadata_fails(client: TestClient) -> None:
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("events.csv", b"timestamp,event_type\n", "text/csv")},
    )
    assert response.status_code == 422


def test_delete_incident(seeded_client: TestClient) -> None:
    response = seeded_client.delete("/api/incidents/INC-2026-0731-004")
    assert response.status_code == 204

    assert (
        seeded_client.get("/api/incidents/INC-2026-0731-004").status_code
        == 404
    )
    remaining = seeded_client.get("/api/incidents").json()
    assert remaining["total"] == 4
    # Cascade: analytics no longer count the deleted incident's category.
    categories = {
        c["category"]
        for c in seeded_client.get("/api/analytics").json()["categories"]
    }
    assert "sensor_dropout" not in categories


def test_delete_missing_incident_404(client: TestClient) -> None:
    assert client.delete("/api/incidents/NOPE").status_code == 404
