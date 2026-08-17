from __future__ import annotations

from fastapi.testclient import TestClient

PRIMARY = "INC-2026-0728-001"
LOCALIZATION = "INC-2026-0729-002"
OSCILLATION = "INC-2026-0730-003"


def test_calibration_empty_without_feedback(seeded_client: TestClient) -> None:
    body = seeded_client.get("/api/analytics").json()
    assert body["calibration"] == []


def test_calibration_precision_from_verdicts(
    seeded_client: TestClient,
) -> None:
    # Two persistent-obstacle-family verdicts: one confirmed, one corrected.
    assert seeded_client.post(
        f"/api/incidents/{PRIMARY}/feedback", json={"verdict": "confirmed"}
    ).status_code == 201
    assert seeded_client.post(
        f"/api/incidents/{LOCALIZATION}/feedback",
        json={"verdict": "confirmed"},
    ).status_code == 201
    assert seeded_client.post(
        f"/api/incidents/{OSCILLATION}/feedback",
        json={
            "verdict": "corrected",
            "actual_category": "persistent_obstacle",
            "note": "Actually a stuck caster against a doorframe.",
        },
    ).status_code == 201

    calibration = seeded_client.get("/api/analytics").json()["calibration"]
    by_category = {c["category"]: c for c in calibration}

    assert by_category["persistent_obstacle"]["reviewed"] == 1
    assert by_category["persistent_obstacle"]["precision"] == 1.0

    oscillation = by_category["controller_oscillation"]
    assert oscillation["reviewed"] == 1
    assert oscillation["confirmed"] == 0
    assert oscillation["precision"] == 0.0
    assert oscillation["corrected_to"] == [
        {"category": "persistent_obstacle", "count": 1}
    ]

    # Sorted by review volume, then category name — all reviewed once here.
    assert [c["reviewed"] for c in calibration] == sorted(
        (c["reviewed"] for c in calibration), reverse=True
    )
