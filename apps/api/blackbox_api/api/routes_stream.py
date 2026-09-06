"""Live streaming ingestion over WebSocket.

Robots connect to /api/stream/{robot_id} and stream events and telemetry
continuously; BlackBox keeps a rolling pre-failure buffer and cuts a
normal incident when a terminal event arrives (or on an explicit "cut"
message). See blackbox_api.ingestion.stream for the message contract.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from blackbox_api.api.auth import OPEN_SCOPE, TokenScope, resolve_token
from blackbox_api.config import get_settings
from blackbox_api.ingestion.service import store_incident
from blackbox_api.ingestion.stream import RobotStream, StreamError
from blackbox_api.logging import log
from blackbox_api.storage.db import session_scope

logger = logging.getLogger("blackbox.stream")

router = APIRouter(tags=["stream"])

#: Application close code for a missing/invalid token (4000-range is
#: reserved for applications by RFC 6455).
UNAUTHORIZED_CLOSE = 4401


def _resolve_scope(websocket: WebSocket) -> TokenScope | None:
    """Authenticate the socket; None means reject.

    Streaming is a write path, so read-only tokens are refused. A
    facility token streams only for its own facility.
    """
    settings = get_settings()
    if (
        not settings.api_token_list
        and not settings.readonly_api_token_list
        and not settings.facility_token_map
    ):
        return OPEN_SCOPE
    provided = websocket.headers.get("x-api-key")
    if provided is None:
        authorization = websocket.headers.get("authorization", "")
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            provided = value.strip()
    if provided is None:
        # Browser WebSocket clients cannot set headers.
        provided = websocket.query_params.get("token")
    if not provided:
        return None
    scope = resolve_token(provided)
    if scope is None or scope.readonly:
        return None
    return scope


def _cut_and_store(
    stream: RobotStream,
    *,
    terminal_event: str | None = None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = request or {}
    incident = stream.cut(
        incident_id=request.get("id"),
        outcome=request.get("outcome"),
        severity=request.get("severity"),
        summary=request.get("summary"),
        terminal_event=terminal_event,
    )
    with session_scope() as session:
        analysis = store_incident(session, incident, source="stream")
    return {
        "type": "incident",
        "incident_id": incident.id,
        "failure_category": analysis.failure_category.value,
        "confidence": analysis.confidence,
        "event_count": len(incident.events),
        "telemetry_channels": len(incident.telemetry),
    }


@router.websocket("/api/stream/{robot_id}")
async def stream_robot(websocket: WebSocket, robot_id: str) -> None:
    scope = _resolve_scope(websocket)
    if scope is None:
        await websocket.close(
            code=UNAUTHORIZED_CLOSE,
            reason="missing, invalid, or read-only API token",
        )
        return
    await websocket.accept()

    window_s = get_settings().stream_window_s
    stream = RobotStream(robot_id=robot_id, window_s=window_s)
    if scope.facility is not None:
        stream.meta["facility"] = scope.facility
    await websocket.send_json({"type": "ready", "window_s": window_s})
    log(logger, logging.INFO, "stream connected", robot_id=robot_id)

    try:
        while True:
            message = await websocket.receive_json()
            try:
                kind = message.get("type")
                if kind == "hello":
                    stream.update_meta(message.get("meta") or {})
                    if scope.facility is not None:
                        # A facility token cannot restamp the tenant.
                        stream.meta["facility"] = scope.facility
                    await websocket.send_json(
                        {"type": "ready", "window_s": window_s}
                    )
                elif kind == "event":
                    terminal = stream.add_event(message)
                    if terminal is not None:
                        await websocket.send_json(
                            _cut_and_store(stream, terminal_event=terminal)
                        )
                elif kind == "sample":
                    stream.add_sample(message)
                elif kind == "cut":
                    await websocket.send_json(
                        _cut_and_store(stream, request=message)
                    )
                else:
                    raise StreamError(f"unknown message type '{kind}'")
            except StreamError as exc:
                await websocket.send_json(
                    {"type": "error", "detail": str(exc)}
                )
    except WebSocketDisconnect:
        log(logger, logging.INFO, "stream disconnected", robot_id=robot_id)
