from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

PRIMARY = "INC-2026-0728-001"


def test_incidents_start_open(seeded_client: TestClient) -> None:
    detail = seeded_client.get(f"/api/incidents/{PRIMARY}").json()
    assert detail["triage_state"] == "open"
    # Untouched incidents have no transition timestamp.
    assert detail["triage_updated_at"] is None
    items = seeded_client.get("/api/incidents").json()["items"]
    assert {i["triage_state"] for i in items} == {"open"}


def test_triage_transitions_and_filtering(seeded_client: TestClient) -> None:
    response = seeded_client.put(
        f"/api/incidents/{PRIMARY}/triage",
        json={"state": "investigating"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == PRIMARY
    assert body["triage_state"] == "investigating"
    # Every transition is timestamped with a recent UTC instant.
    first_touch = datetime.fromisoformat(body["triage_updated_at"])
    assert abs((datetime.now(UTC) - first_touch).total_seconds()) < 60

    investigating = seeded_client.get(
        "/api/incidents", params={"triage": "investigating"}
    ).json()
    assert [i["id"] for i in investigating["items"]] == [PRIMARY]
    assert (
        seeded_client.get(
            "/api/incidents", params={"triage": "open"}
        ).json()["total"]
        == 4
    )

    seeded_client.put(
        f"/api/incidents/{PRIMARY}/triage", json={"state": "resolved"}
    )
    detail = seeded_client.get(f"/api/incidents/{PRIMARY}").json()
    assert detail["triage_state"] == "resolved"
    resolved_at = datetime.fromisoformat(detail["triage_updated_at"])
    assert resolved_at >= first_touch


def test_triage_validation_and_404(seeded_client: TestClient) -> None:
    assert (
        seeded_client.put(
            f"/api/incidents/{PRIMARY}/triage", json={"state": "nope"}
        ).status_code
        == 422
    )
    assert (
        seeded_client.put(
            "/api/incidents/NOPE/triage", json={"state": "resolved"}
        ).status_code
        == 404
    )
