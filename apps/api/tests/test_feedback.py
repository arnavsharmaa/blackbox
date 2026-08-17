from __future__ import annotations

from fastapi.testclient import TestClient

PRIMARY = "INC-2026-0728-001"


def test_confirm_diagnosis(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback",
        json={"verdict": "confirmed", "note": "Pallet found in aisle C."},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["verdict"] == "confirmed"
    assert body["diagnosed_category"] == "persistent_obstacle"
    assert body["actual_category"] is None
    assert body["note"] == "Pallet found in aisle C."

    # The verdict rides along with the incident detail.
    detail = seeded_client.get(f"/api/incidents/{PRIMARY}").json()
    assert detail["feedback"]["verdict"] == "confirmed"


def test_correct_diagnosis_and_resubmit_replaces(
    seeded_client: TestClient,
) -> None:
    first = seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback",
        json={"verdict": "corrected", "actual_category": "sensor_dropout"},
    )
    assert first.status_code == 201
    assert first.json()["actual_category"] == "sensor_dropout"

    second = seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback",
        json={"verdict": "confirmed"},
    )
    assert second.status_code == 201
    detail = seeded_client.get(f"/api/incidents/{PRIMARY}").json()
    assert detail["feedback"]["verdict"] == "confirmed"
    assert detail["feedback"]["actual_category"] is None


def test_corrected_requires_actual_category(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback",
        json={"verdict": "corrected"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("actual_category" in e["error"] for e in detail["errors"])


def test_confirmed_rejects_actual_category(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback",
        json={"verdict": "confirmed", "actual_category": "sensor_dropout"},
    )
    assert response.status_code == 422


def test_feedback_missing_incident_404(seeded_client: TestClient) -> None:
    response = seeded_client.post(
        "/api/incidents/NOPE/feedback", json={"verdict": "confirmed"}
    )
    assert response.status_code == 404


def test_feedback_deleted_with_incident(seeded_client: TestClient) -> None:
    seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback", json={"verdict": "confirmed"}
    )
    assert seeded_client.delete(f"/api/incidents/{PRIMARY}").status_code == 204
    assert seeded_client.get(f"/api/incidents/{PRIMARY}").status_code == 404
