from __future__ import annotations

import copy
import json

from fastapi.testclient import TestClient

PRIMARY = "INC-2026-0728-001"


def _upload_repeat(client: TestClient) -> None:
    base = client.get(f"/api/incidents/{PRIMARY}").json()["incident"]
    repeat = copy.deepcopy(base)
    repeat["id"] = "INC-2026-0804-009"
    repeat["robot_id"] = "W-207"
    repeat["start_time"] = "2026-08-04T09:14:03+00:00"
    repeat["end_time"] = "2026-08-04T09:15:35+00:00"
    for event in repeat["events"]:
        event["timestamp"] = event["timestamp"].replace("-07-28", "-08-04")
    response = client.post(
        "/api/incidents/upload",
        files={
            "file": (
                "repeat.json",
                json.dumps(repeat).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text


def test_no_similar_incidents_for_a_one_off(
    seeded_client: TestClient,
) -> None:
    assert (
        seeded_client.get(f"/api/incidents/{PRIMARY}/similar").json() == []
    )


def test_similar_finds_the_same_signature(seeded_client: TestClient) -> None:
    _upload_repeat(seeded_client)

    similar = seeded_client.get(f"/api/incidents/{PRIMARY}/similar").json()
    assert [s["id"] for s in similar] == ["INC-2026-0804-009"]
    assert similar[0]["failure_category"] == "persistent_obstacle"

    # Symmetric from the repeat's side; never includes itself.
    from_repeat = seeded_client.get(
        "/api/incidents/INC-2026-0804-009/similar"
    ).json()
    assert [s["id"] for s in from_repeat] == [PRIMARY]

    # The successful baseline shares the task but not the category
    # (unknown), so it appears in neither list and returns [] itself.
    assert (
        seeded_client.get(
            "/api/incidents/INC-2026-0721-BASE/similar"
        ).json()
        == []
    )


def test_similar_missing_incident_404(seeded_client: TestClient) -> None:
    assert (
        seeded_client.get("/api/incidents/NOPE/similar").status_code == 404
    )
