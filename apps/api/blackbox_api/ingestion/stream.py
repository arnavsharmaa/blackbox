"""Rolling pre-failure buffers for live streaming ingestion.

A robot streams events and telemetry samples continuously; BlackBox keeps
only the most recent window (BLACKBOX_STREAM_WINDOW_S, default 10 min).
When a terminal event arrives — or the client asks for a cut — the buffer
becomes a normal Incident and flows through the same validate → persist →
analyze pipeline as file uploads. Nothing is stored for runs that never
fail.

Message contract (JSON over the /api/stream WebSocket):

- ``{"type": "hello", "meta": {...}}`` — optional incident metadata
  (robot_model, facility, task_name, task_goal, software_version,
  map_version, environment); unknown fields are ignored.
- ``{"type": "event", "t": <unix seconds>, "event_type": ...,
  "subsystem": ..., "message": ..., "severity"?, "payload"?,
  "correlation_id"?, "evidence_tags"?}``
- ``{"type": "sample", "t": <unix seconds>, "channel": ...,
  "value": ..., "unit"?}``
- ``{"type": "cut", "id"?, "outcome"?, "severity"?, "summary"?}`` —
  force an incident from the current buffer (e.g. for near-misses).

Events of type task_failed / task_timed_out cut automatically.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from blackbox_api.schemas import EventType, Incident, TelemetryChannel

#: Terminal event types and the incident outcome/severity they imply.
TERMINAL_EVENTS: dict[str, tuple[str, str]] = {
    "task_failed": ("failed", "critical"),
    "task_timed_out": ("timed_out", "error"),
}

_EVENT_TYPES = {e.value for e in EventType}
_CHANNELS = {c.value for c in TelemetryChannel}

_META_FIELDS = (
    "robot_model",
    "facility",
    "task_name",
    "task_goal",
    "software_version",
    "map_version",
    "environment",
)


class StreamError(Exception):
    """A client-visible problem with a streamed message or cut."""


def _require_time(msg: dict[str, Any]) -> float:
    t = msg.get("t")
    if not isinstance(t, (int, float)) or isinstance(t, bool):
        raise StreamError("'t' must be a unix timestamp in seconds")
    return float(t)


@dataclass
class RobotStream:
    """The rolling buffer for one connected robot."""

    robot_id: str
    window_s: float
    meta: dict[str, Any] = field(default_factory=dict)
    _events: deque[dict[str, Any]] = field(default_factory=deque)
    _samples: deque[dict[str, Any]] = field(default_factory=deque)

    def update_meta(self, meta: dict[str, Any]) -> None:
        self.meta.update(
            {k: v for k, v in meta.items() if k in _META_FIELDS and v}
        )

    def add_event(self, msg: dict[str, Any]) -> str | None:
        """Buffer one event; returns the event type if it is terminal."""
        t = _require_time(msg)
        event_type = msg.get("event_type")
        if event_type not in _EVENT_TYPES:
            raise StreamError(f"unknown event_type '{event_type}'")
        for key in ("subsystem", "message"):
            if not msg.get(key):
                raise StreamError(f"event is missing '{key}'")
        self._events.append({**msg, "t": t})
        self._trim(t)
        return event_type if event_type in TERMINAL_EVENTS else None

    def add_sample(self, msg: dict[str, Any]) -> None:
        t = _require_time(msg)
        channel = msg.get("channel")
        if channel not in _CHANNELS:
            raise StreamError(f"unknown telemetry channel '{channel}'")
        if "value" not in msg:
            raise StreamError("sample is missing 'value'")
        self._samples.append({**msg, "t": t})
        self._trim(t)

    def _trim(self, now: float) -> None:
        horizon = now - self.window_s
        while self._events and self._events[0]["t"] < horizon:
            self._events.popleft()
        while self._samples and self._samples[0]["t"] < horizon:
            self._samples.popleft()

    def cut(
        self,
        *,
        incident_id: str | None = None,
        outcome: str | None = None,
        severity: str | None = None,
        summary: str | None = None,
        terminal_event: str | None = None,
    ) -> Incident:
        """Turn the buffered window into a validated Incident and reset."""
        if not self._events:
            raise StreamError("no buffered events to cut an incident from")

        implied_outcome, implied_severity = TERMINAL_EVENTS.get(
            terminal_event or "", ("failed", "error")
        )
        events = sorted(self._events, key=lambda e: e["t"])
        samples = sorted(self._samples, key=lambda s: s["t"])
        start_t = min(
            events[0]["t"], samples[0]["t"] if samples else events[0]["t"]
        )
        end_t = max(
            events[-1]["t"], samples[-1]["t"] if samples else events[-1]["t"]
        )
        end_t = max(end_t, start_t + 1.0)

        def iso(t: float) -> str:
            return datetime.fromtimestamp(t, UTC).isoformat()

        by_channel: dict[str, list[dict[str, Any]]] = {}
        for sample in samples:
            by_channel.setdefault(sample["channel"], []).append(sample)

        payload = {
            "schema_version": "1.0",
            "id": incident_id
            or f"INC-STREAM-{self.robot_id}-{int(start_t)}",
            "robot_id": self.robot_id,
            "robot_model": self.meta.get("robot_model", "unknown"),
            "facility": self.meta.get("facility", "unknown"),
            "task_name": self.meta.get("task_name", "Streamed task"),
            "task_goal": self.meta.get("task_goal", "unknown"),
            "start_time": iso(start_t),
            "end_time": iso(end_t),
            "outcome": outcome or implied_outcome,
            "severity": severity or implied_severity,
            "software_version": self.meta.get("software_version", "unknown"),
            "map_version": self.meta.get("map_version", "unknown"),
            "environment": self.meta.get("environment", "unknown"),
            "summary": summary
            or f"Incident cut from the live stream of {self.robot_id} "
            f"({len(events)} events in the {self.window_s:.0f} s window).",
            "events": [
                {
                    "timestamp": iso(e["t"]),
                    "event_type": e["event_type"],
                    "subsystem": e["subsystem"],
                    "severity": e.get("severity", "info"),
                    "message": e["message"],
                    "payload": e.get("payload", {}),
                    "correlation_id": e.get("correlation_id"),
                    "evidence_tags": e.get("evidence_tags", []),
                }
                for e in events
            ],
            "telemetry": [
                {
                    "channel": channel,
                    "unit": chan_samples[0].get("unit", ""),
                    "samples": [
                        {"t": round(s["t"] - start_t, 3), "value": s["value"]}
                        for s in chan_samples
                    ],
                }
                for channel, chan_samples in by_channel.items()
            ],
        }
        try:
            incident = Incident.model_validate(payload)
        except ValidationError as exc:
            raise StreamError(
                "buffered stream does not form a valid incident: "
                + "; ".join(
                    f"{'/'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                )
            ) from exc
        self._events.clear()
        self._samples.clear()
        return incident
