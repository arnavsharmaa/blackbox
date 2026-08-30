from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from blackbox_api.config import get_settings

BASE_T = 1_785_000_000.0


def _blocked_run(ws) -> None:  # type: ignore[no-untyped-def]
    """Stream a minimal blocked-robot run ending in task_failed."""
    ws.send_json({
        "type": "hello",
        "meta": {
            "robot_model": "Fetchbot AMR-600",
            "facility": "Warehouse 9",
            "task_name": "Streamed delivery",
        },
    })
    assert ws.receive_json()["type"] == "ready"
    ws.send_json({
        "t": BASE_T, "type": "event", "event_type": "task_started",
        "subsystem": "task_manager", "message": "Task started",
    })
    for i in range(30):
        t = BASE_T + 1.0 + i
        ws.send_json({
            "type": "sample", "t": t, "channel": "obstacle_distance",
            "value": 0.4, "unit": "m",
        })
        ws.send_json({
            "type": "event", "t": t, "event_type": "velocity_command",
            "subsystem": "controller", "message": "cmd_vel 0.0",
            "payload": {"linear": 0.0, "angular": 0.0},
        })
    ws.send_json({
        "type": "event", "t": BASE_T + 31.0, "event_type": "task_failed",
        "subsystem": "task_manager", "severity": "critical",
        "message": "Task failed while blocked",
    })


def test_terminal_event_cuts_and_persists(client: TestClient) -> None:
    with client.websocket_connect("/api/stream/W-500") as ws:
        assert ws.receive_json()["type"] == "ready"
        _blocked_run(ws)
        result = ws.receive_json()

    assert result["type"] == "incident"
    assert result["incident_id"].startswith("INC-STREAM-W-500-")
    assert result["event_count"] == 32

    # The incident is queryable through the normal REST API.
    detail = client.get(f"/api/incidents/{result['incident_id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["incident"]["robot_id"] == "W-500"
    assert body["analysis"] is not None


def test_explicit_cut_flags_a_near_miss(client: TestClient) -> None:
    with client.websocket_connect("/api/stream/W-501") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({
            "type": "event", "t": BASE_T, "event_type": "warning_raised",
            "subsystem": "perception", "severity": "warning",
            "message": "Close call near dock 4",
        })
        ws.send_json({
            "type": "cut", "id": "INC-NEAR-MISS-9", "outcome": "success",
            "severity": "warning", "summary": "Operator-flagged near-miss",
        })
        result = ws.receive_json()

    assert result["incident_id"] == "INC-NEAR-MISS-9"
    assert client.get("/api/incidents/INC-NEAR-MISS-9").status_code == 200


def test_bad_messages_get_error_frames_and_stream_survives(
    client: TestClient,
) -> None:
    with client.websocket_connect("/api/stream/W-502") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "teleport"})
        assert "unknown message type" in ws.receive_json()["detail"]
        ws.send_json({
            "type": "event", "t": BASE_T, "event_type": "robot_exploded",
            "subsystem": "task_manager", "message": "boom",
        })
        assert "unknown event_type" in ws.receive_json()["detail"]
        ws.send_json({"type": "cut"})
        assert "no buffered events" in ws.receive_json()["detail"]
        # The connection is still usable after errors.
        ws.send_json({
            "type": "event", "t": BASE_T, "event_type": "task_failed",
            "subsystem": "task_manager", "severity": "critical",
            "message": "failed",
        })
        assert ws.receive_json()["type"] == "incident"


def test_stream_requires_token_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLACKBOX_API_TOKENS", "sekret-1")
    get_settings.cache_clear()

    with pytest.raises(WebSocketDisconnect) as excinfo, \
            client.websocket_connect("/api/stream/W-503"):
        pass
    assert excinfo.value.code == 4401

    # A query-param token works (browser clients cannot set headers).
    with client.websocket_connect("/api/stream/W-503?token=sekret-1") as ws:
        assert ws.receive_json()["type"] == "ready"
