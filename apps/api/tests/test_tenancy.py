from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from blackbox_api.config import get_settings

FREMONT = "Warehouse 3 — Fremont"
CHICAGO = "Warehouse 7 — Chicago"
PRIMARY = "INC-2026-0728-001"

FREMONT_TOK = {"Authorization": "Bearer fremont-tok"}
CHICAGO_TOK = {"Authorization": "Bearer chicago-tok"}
ADMIN_TOK = {"Authorization": "Bearer admin-tok"}


@pytest.fixture()
def tenants(
    seeded_client: TestClient,
    sample_incidents: dict[str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Five Fremont samples plus one Chicago incident, tokens per facility."""
    chicago = copy.deepcopy(sample_incidents["oscillation"])
    chicago["id"] = "INC-CHI-001"
    chicago["facility"] = CHICAGO
    response = seeded_client.post(
        "/api/incidents/upload",
        files={
            "file": (
                "chi.json",
                json.dumps(chicago).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text

    monkeypatch.setenv("BLACKBOX_API_TOKENS", "admin-tok")
    monkeypatch.setenv(
        "BLACKBOX_FACILITY_TOKENS",
        json.dumps({"fremont-tok": FREMONT, "chicago-tok": CHICAGO}),
    )
    get_settings.cache_clear()
    return seeded_client


def test_list_is_scoped_to_the_token_facility(tenants: TestClient) -> None:
    fremont = tenants.get("/api/incidents", headers=FREMONT_TOK).json()
    assert fremont["total"] == 5
    assert {i["facility"] for i in fremont["items"]} == {FREMONT}

    chicago = tenants.get("/api/incidents", headers=CHICAGO_TOK).json()
    assert chicago["total"] == 1
    assert chicago["items"][0]["id"] == "INC-CHI-001"

    # An explicit facility param cannot escape the token's scope.
    sneaky = tenants.get(
        "/api/incidents",
        headers=CHICAGO_TOK,
        params={"facility": FREMONT},
    ).json()
    assert sneaky["total"] == 1
    assert sneaky["items"][0]["facility"] == CHICAGO

    # Full tokens still see everything.
    assert tenants.get("/api/incidents", headers=ADMIN_TOK).json()["total"] == 6


def test_cross_facility_reads_look_missing(tenants: TestClient) -> None:
    assert (
        tenants.get(f"/api/incidents/{PRIMARY}", headers=CHICAGO_TOK).status_code
        == 404
    )
    for suffix in ("events", "telemetry", "analysis", "report", "github-issue"):
        assert (
            tenants.get(
                f"/api/incidents/{PRIMARY}/{suffix}", headers=CHICAGO_TOK
            ).status_code
            == 404
        ), suffix
    # The same requests succeed inside the token's own facility.
    assert (
        tenants.get(f"/api/incidents/{PRIMARY}", headers=FREMONT_TOK).status_code
        == 200
    )
    assert (
        tenants.get("/api/incidents/INC-CHI-001", headers=CHICAGO_TOK).status_code
        == 200
    )


def test_diff_cannot_cross_facilities(tenants: TestClient) -> None:
    response = tenants.get(
        f"/api/incidents/INC-CHI-001/diff/{PRIMARY}", headers=CHICAGO_TOK
    )
    assert response.status_code == 404


def test_upload_is_pinned_to_the_token_facility(
    tenants: TestClient, sample_incidents: dict[str, Any]
) -> None:
    foreign = copy.deepcopy(sample_incidents["sensor_dropout"])
    foreign["id"] = "INC-SNEAK-001"
    # Facility stays Fremont — a Chicago token may not upload it.
    response = tenants.post(
        "/api/incidents/upload",
        headers=CHICAGO_TOK,
        files={
            "file": (
                "sneak.json",
                json.dumps(foreign).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 403
    assert "Warehouse 7 — Chicago" in response.json()["detail"]
    assert (
        tenants.get("/api/incidents/INC-SNEAK-001", headers=ADMIN_TOK).status_code
        == 404
    )


def test_delete_and_feedback_cannot_cross_facilities(
    tenants: TestClient,
) -> None:
    assert (
        tenants.delete(
            f"/api/incidents/{PRIMARY}", headers=CHICAGO_TOK
        ).status_code
        == 404
    )
    assert (
        tenants.post(
            f"/api/incidents/{PRIMARY}/feedback",
            headers=CHICAGO_TOK,
            json={"verdict": "confirmed"},
        ).status_code
        == 404
    )
    # The incident is untouched for its own tenant.
    assert (
        tenants.get(f"/api/incidents/{PRIMARY}", headers=FREMONT_TOK).status_code
        == 200
    )


def test_prune_is_scoped_to_the_token_facility(tenants: TestClient) -> None:
    # A Chicago token pruning everything only removes Chicago incidents.
    result = tenants.delete(
        "/api/incidents",
        headers=CHICAGO_TOK,
        params={"before": "2030-01-01T00:00:00Z"},
    ).json()
    assert result == {"deleted": 1, "incident_ids": ["INC-CHI-001"]}
    assert (
        tenants.get("/api/incidents", headers=ADMIN_TOK).json()["total"] == 5
    )


def test_stream_rejects_readonly_and_stamps_facility(
    tenants: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setenv("BLACKBOX_READONLY_TOKENS", "viewer-1")
    get_settings.cache_clear()

    with pytest.raises(WebSocketDisconnect) as excinfo, \
            tenants.websocket_connect("/api/stream/W-900?token=viewer-1"):
        pass
    assert excinfo.value.code == 4401

    # A facility token streams, and its cut is stamped with its facility
    # even when the hello claims another one.
    with tenants.websocket_connect(
        "/api/stream/W-900?token=chicago-tok"
    ) as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "hello", "meta": {"facility": FREMONT}})
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({
            "type": "event", "t": 1_785_000_000.0,
            "event_type": "task_failed", "subsystem": "task_manager",
            "severity": "critical", "message": "failed",
        })
        cut = ws.receive_json()
    assert cut["type"] == "incident"
    detail = tenants.get(
        f"/api/incidents/{cut['incident_id']}", headers=ADMIN_TOK
    ).json()
    assert detail["incident"]["facility"] == CHICAGO


def test_analytics_are_scoped_to_the_token_facility(
    tenants: TestClient,
) -> None:
    tenants.post(
        "/api/incidents/INC-CHI-001/feedback",
        headers=CHICAGO_TOK,
        json={"verdict": "confirmed"},
    )
    chicago = tenants.get("/api/analytics", headers=CHICAGO_TOK).json()
    assert chicago["total_incidents"] == 1
    assert chicago["by_robot"][0]["robot_id"] == "W-231"
    assert [c["category"] for c in chicago["calibration"]] == [
        "controller_oscillation"
    ]

    fremont = tenants.get("/api/analytics", headers=FREMONT_TOK).json()
    assert fremont["total_incidents"] == 5
    assert fremont["calibration"] == []

    # Full tokens can still slice by facility explicitly.
    sliced = tenants.get(
        "/api/analytics",
        headers=ADMIN_TOK,
        params={"facility": "Warehouse 7 — Chicago"},
    ).json()
    assert sliced["total_incidents"] == 1
