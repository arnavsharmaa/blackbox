"""rosbag2 (MCAP) ingestion adapter.

Reads a ROS 2 bag recorded in the MCAP container format (``ros2 bag record -s
mcap``, the default storage plugin on recent distros) and converts the topics
in blackbox_api.ros2_mapping into a canonical Incident. Decoding uses the
pure-Python ``mcap`` + ``mcap-ros2-support`` packages — no ROS installation is
required.

Bags carry no fleet metadata, so uploads must supply a metadata JSON part
with at least ``id`` and ``robot_id`` (all other incident fields have
defaults and may be overridden). ``start_time`` in the metadata re-bases the
incident clock; all message times stay relative to the first message.
"""

from __future__ import annotations

import io
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from blackbox_api.ingestion.base import IncidentAdapter, IngestError
from blackbox_api.ingestion.json_adapter import format_validation_error
from blackbox_api.ros2_mapping import (
    GOAL_STATUS_TO_EVENT,
    amcl_to_confidence,
    odom_to_samples,
    scan_to_obstacle_distance,
)
from blackbox_api.schemas import Incident

SUPPORTED_TOPICS = (
    "/odom",
    "/cmd_vel",
    "/scan",
    "/amcl_pose",
    "/navigate_to_pose/_action/status",
)

# Downsampling intervals (seconds) keep incidents at replay-friendly rates.
ODOM_SAMPLE_S = 0.2
SCAN_SAMPLE_S = 0.5
AMCL_SAMPLE_S = 0.5
CMD_EVENT_S = 0.9
POSE_EVENT_S = 4.5

METADATA_DEFAULTS: dict[str, str] = {
    "robot_model": "unknown",
    "facility": "unknown",
    "task_name": "navigate_to_pose",
    "task_goal": "Recorded ROS 2 navigation goal",
    "software_version": "unknown",
    "map_version": "unknown",
    "environment": "ROS 2 bag capture",
    "severity": "error",
}


def _ros_msg_to_dict(obj: object) -> Any:
    """Decoded mcap-ros2 message → plain nested dict/list structure."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return list(obj)
    if isinstance(obj, (list, tuple)):
        return [_ros_msg_to_dict(item) for item in obj]
    fields = getattr(obj, "__slots__", None)
    if fields is None:
        fields = list(vars(obj).keys())
    return {
        str(name).lstrip("_"): _ros_msg_to_dict(getattr(obj, name))
        for name in fields
    }


class _Downsampler:
    """Keeps at most one value per ``interval`` seconds."""

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._last: float | None = None

    def accept(self, t: float) -> bool:
        if self._last is not None and t - self._last < self.interval:
            return False
        self._last = t
        return True


class Rosbag2Adapter(IncidentAdapter):
    name = "rosbag2"
    extensions = (".mcap",)

    def parse(self, raw: bytes, *, metadata: dict[str, Any] | None = None) -> Incident:
        try:
            from mcap.reader import make_reader
            from mcap_ros2.decoder import DecoderFactory
        except ImportError as exc:
            raise IngestError(
                "rosbag2 ingestion requires the 'mcap' and 'mcap-ros2-support' "
                "packages (pip install mcap mcap-ros2-support)"
            ) from exc

        if not metadata or not metadata.get("id") or not metadata.get("robot_id"):
            raise IngestError(
                "MCAP uploads require a metadata JSON part with at least "
                "'id' and 'robot_id' (bags carry no fleet metadata); other "
                "incident fields are optional overrides"
            )

        try:
            reader = make_reader(
                io.BytesIO(raw), decoder_factories=[DecoderFactory()]
            )
            decoded = [
                (channel.topic, message.log_time, ros_msg)
                for _schema, channel, message, ros_msg in
                reader.iter_decoded_messages(topics=list(SUPPORTED_TOPICS))
            ]
        except IngestError:
            raise
        except Exception as exc:  # mcap raises assorted error types on bad input
            raise IngestError(
                f"file is not a readable MCAP bag: {exc}"
            ) from exc
        if not decoded:
            raise IngestError(
                "bag contains none of the supported topics: "
                + ", ".join(SUPPORTED_TOPICS)
            )
        decoded.sort(key=lambda item: item[1])
        return self._assemble(decoded, dict(metadata))

    def _assemble(
        self,
        decoded: list[tuple[str, int, object]],
        metadata: dict[str, Any],
    ) -> Incident:
        t0_ns = decoded[0][1]
        t_last = (decoded[-1][1] - t0_ns) / 1e9

        start_override = metadata.pop("start_time", None)
        metadata.pop("end_time", None)  # always derived from the bag span
        if start_override is not None:
            try:
                base = datetime.fromisoformat(
                    str(start_override).replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise IngestError(
                    f"metadata start_time is not an ISO timestamp: "
                    f"{start_override!r}"
                ) from exc
        else:
            base = datetime.fromtimestamp(t0_ns / 1e9, tz=UTC)

        def iso(t: float) -> str:
            return (base + timedelta(seconds=t)).isoformat()

        samples: dict[str, list[dict[str, float]]] = {}

        def record(channel: str, t: float, value: float) -> None:
            samples.setdefault(channel, []).append(
                {"t": round(t, 3), "value": round(value, 4)}
            )

        events: list[dict[str, Any]] = []

        def event(
            t: float,
            event_type: str,
            subsystem: str,
            message: str,
            severity: str = "info",
            payload: dict[str, Any] | None = None,
        ) -> None:
            events.append({
                "timestamp": iso(t),
                "event_type": event_type,
                "subsystem": subsystem,
                "severity": severity,
                "message": message,
                "payload": payload or {},
                "correlation_id": None,
                "evidence_tags": [],
            })

        odom_ds = _Downsampler(ODOM_SAMPLE_S)
        scan_ds = _Downsampler(SCAN_SAMPLE_S)
        amcl_ds = _Downsampler(AMCL_SAMPLE_S)
        cmd_ds = _Downsampler(CMD_EVENT_S)
        pose_ev_ds = _Downsampler(POSE_EVENT_S)
        last_status: int | None = None
        outcome = "failed"
        goal_seen = False

        event(
            0.0,
            "task_started",
            "task_manager",
            f"Task '{metadata.get('task_name', 'navigate_to_pose')}' started "
            "(imported from rosbag2 capture)",
        )

        for topic, log_time, ros_msg in decoded:
            t = (log_time - t0_ns) / 1e9
            msg = _ros_msg_to_dict(ros_msg)

            if topic == "/odom" and odom_ds.accept(t):
                for channel, value in odom_to_samples(msg).items():
                    record(channel, t, value)
                if pose_ev_ds.accept(t):
                    position = msg["pose"]["pose"]["position"]
                    event(
                        t, "pose_updated", "localization",
                        f"Pose ({position['x']:.2f}, {position['y']:.2f})",
                        payload={
                            "x": round(float(position["x"]), 3),
                            "y": round(float(position["y"]), 3),
                        },
                    )
            elif topic == "/cmd_vel" and cmd_ds.accept(t):
                linear = float(msg["linear"]["x"])
                angular = float(msg["angular"]["z"])
                event(
                    t, "velocity_command", "controller",
                    f"cmd_vel linear={linear:.2f} m/s angular={angular:.2f} rad/s",
                    payload={"linear": linear, "angular": angular},
                )
            elif topic == "/scan" and scan_ds.accept(t):
                clearance = scan_to_obstacle_distance(msg)
                if math.isfinite(clearance):
                    record("obstacle_distance", t, clearance)
            elif topic == "/amcl_pose" and amcl_ds.accept(t):
                record("localization_confidence", t, amcl_to_confidence(msg))
            elif topic == "/navigate_to_pose/_action/status":
                status_list = msg.get("status_list") or []
                if not status_list:
                    continue
                code = int(status_list[-1]["status"])
                if code == last_status:
                    continue
                last_status = code
                event_type, mapped_outcome = GOAL_STATUS_TO_EVENT.get(
                    code, (None, "success")
                )
                if event_type == "nav_goal_issued" and not goal_seen:
                    goal_seen = True
                    event(
                        t, "nav_goal_issued", "navigation",
                        "navigate_to_pose goal accepted",
                        payload={"goal_status": code},
                    )
                elif event_type == "task_failed":
                    outcome = mapped_outcome
                    event(
                        t, "task_failed", "task_manager",
                        f"navigate_to_pose goal ended with status {code} "
                        f"({mapped_outcome})",
                        severity="error",
                        payload={"goal_status": code},
                    )
                elif event_type is None and code == 4:
                    outcome = "success"
                    event(
                        t, "planner_state_changed", "planner",
                        "navigate_to_pose goal succeeded",
                        payload={"state": "succeeded", "goal_status": code},
                    )

        telemetry = [
            {"channel": channel, "unit": _UNIT_BY_CHANNEL.get(channel, ""),
             "samples": series}
            for channel, series in samples.items()
        ]

        robot_id = str(metadata.pop("robot_id"))
        data: dict[str, Any] = {
            "id": str(metadata.pop("id")),
            "robot_id": robot_id,
            "start_time": iso(0.0),
            # Incidents must span their events; pad past the last message.
            "end_time": iso(max(t_last, 1.0) + 0.5),
            "outcome": outcome,
            "summary": f"Imported from a rosbag2 (MCAP) capture of robot "
                       f"{robot_id}: navigate_to_pose task ended with "
                       f"outcome '{outcome}' after {t_last:.0f} s.",
            **METADATA_DEFAULTS,
            "events": events,
            "telemetry": telemetry,
        }
        data.update(metadata)  # explicit metadata overrides the defaults

        try:
            return Incident.model_validate(data)
        except ValidationError as exc:
            raise IngestError(
                "incident assembled from the bag failed schema validation",
                details=format_validation_error(exc),
            ) from exc


_UNIT_BY_CHANNEL = {
    "pos_x": "m",
    "pos_y": "m",
    "heading": "rad",
    "linear_velocity": "m/s",
    "angular_velocity": "rad/s",
    "obstacle_distance": "m",
    "localization_confidence": "",
}
