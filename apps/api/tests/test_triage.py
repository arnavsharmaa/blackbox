from __future__ import annotations

from fastapi.testclient import TestClient

PRIMARY = "INC-2026-0728-001"


def test_incidents_start_open(seeded_client: TestClient) -> None:
    detail = seeded_client.get(f"/api/incidents/{PRIMARY}").json()
    assert detail["triage_state"] == "open"
    items = seeded_client.get("/api/incidents").json()["items"]
    assert {i["triage_state"] for i in items} == {"open"}


def test_triage_transitions_and_filtering(seeded_client: TestClient) -> None:
    response = seeded_client.put(
        f"/api/incidents/{PRIMARY}/triage",
        json={"state": "investigating"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "incident_id": PRIMARY,
        "triage_state": "investigating",
    }

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
