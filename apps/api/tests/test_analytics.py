from __future__ import annotations

from fastapi.testclient import TestClient


def test_analytics_empty_database(client: TestClient) -> None:
    body = client.get("/api/analytics").json()
    assert body["total_incidents"] == 0
    assert body["categories"] == []
    assert body["by_robot"] == []
    assert body["blockage_hotspots"] == []


def test_analytics_aggregates_seeded_fleet(seeded_client: TestClient) -> None:
    response = seeded_client.get("/api/analytics")
    assert response.status_code == 200
    body = response.json()

    assert body["total_incidents"] == 4
    assert body["critical_incidents"] == 1
    # Primary incident carries the fleet's three recovery attempts, the
    # localization incident one more.
    assert body["total_recovery_attempts"] == 4

    categories = {c["category"]: c["count"] for c in body["categories"]}
    assert categories == {
        "persistent_obstacle": 1,
        "localization_failure": 1,
        "controller_oscillation": 1,
        "sensor_dropout": 1,
    }

    outcomes = {o["outcome"]: o["count"] for o in body["outcomes"]}
    assert outcomes == {"failed": 2, "timed_out": 1, "aborted": 1}

    robots = {r["robot_id"]: r for r in body["by_robot"]}
    assert set(robots) == {"W-104", "W-087", "W-231", "W-058"}
    assert robots["W-104"]["critical"] == 1
    assert robots["W-104"]["top_category"] == "persistent_obstacle"
    assert robots["W-104"]["recovery_attempts"] == 3

    versions = body["by_software_version"]
    assert len(versions) == 1
    assert versions[0]["software_version"] == "nav-stack 2.14.1"
    assert versions[0]["incidents"] == 4
    assert len(versions[0]["categories"]) == 4


def test_analytics_blockage_hotspots(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/analytics").json()
    hotspots = body["blockage_hotspots"]
    # Only the persistent-obstacle incident contributes a blockage location.
    assert len(hotspots) == 1
    spot = hotspots[0]
    assert spot["facility"] == "Warehouse 3 — Fremont"
    assert spot["x"] == 13.5
    assert abs(spot["y"] - 5.5) < 0.51  # snapped to the 0.5 m grid
    assert spot["incident_ids"] == ["INC-2026-0728-001"]


def test_analytics_daily_trend(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/analytics").json()
    daily = body["daily"]
    # Four incidents on four distinct days, one category each.
    assert len(daily) == 4
    assert [d["date"] for d in daily] == sorted(d["date"] for d in daily)
    assert {d["count"] for d in daily} == {1}
