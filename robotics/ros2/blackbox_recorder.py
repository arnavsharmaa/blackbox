#!/usr/bin/env python3
"""Example ROS 2 recorder node that ships failed navigation tasks to BlackBox.

Requires a ROS 2 environment (rclpy + Nav2 message packages) and `requests`.
Outside ROS this file only documents the integration — it exits with a clear
message instead of crashing. See robotics/ros2/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))

from ros2_topic_mapping import (  # noqa: E402
    GOAL_STATUS_TO_EVENT,
    amcl_to_confidence,
    odom_to_samples,
    scan_to_obstacle_distance,
)

try:
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
    from action_msgs.msg import GoalStatusArray
except ImportError:
    rclpy = None
    Node = object  # type: ignore[assignment,misc]


SAMPLE_PERIOD_S = 0.2
BUFFER_S = 180.0


class BlackboxRecorder(Node):  # type: ignore[misc]
    """Rolling recorder: converts topics to canonical samples, uploads on failure."""

    def __init__(self, api: str, robot_id: str, facility: str) -> None:
        super().__init__("blackbox_recorder")
        self.api = api
        self.robot_id = robot_id
        self.facility = facility
        self.samples: dict[str, list[dict]] = {}
        self.events: list[dict] = []
        self.task_started_at: datetime | None = None
        self._last_sample: dict[str, float] = {}

        self.create_subscription(Odometry, "/odom", self.on_odom, 20)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 20)
        self.create_subscription(LaserScan, "/scan", self.on_scan, 10)
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self.on_amcl, 10
        )
        self.create_subscription(
            GoalStatusArray, "/navigate_to_pose/_action/status",
            self.on_goal_status, 10,
        )

    # -- topic handlers convert with the pure mapping helpers ----------------

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _record(self, channel: str, value: float) -> None:
        t = self._now().timestamp()
        buf = self.samples.setdefault(channel, [])
        if buf and t - buf[-1]["abs_t"] < SAMPLE_PERIOD_S:
            return
        buf.append({"abs_t": t, "value": round(float(value), 4)})
        cutoff = t - BUFFER_S
        while buf and buf[0]["abs_t"] < cutoff:
            buf.pop(0)

    def on_odom(self, msg: object) -> None:
        for channel, value in odom_to_samples(_msg_to_dict(msg)).items():
            self._record(channel, value)

    def on_cmd_vel(self, msg: object) -> None:
        data = _msg_to_dict(msg)
        self.events.append({
            "timestamp": self._now().isoformat(),
            "event_type": "velocity_command",
            "subsystem": "controller",
            "severity": "info",
            "message": "cmd_vel from /cmd_vel",
            "payload": {
                "linear": data["linear"]["x"],
                "angular": data["angular"]["z"],
            },
            "correlation_id": None,
            "evidence_tags": [],
        })

    def on_scan(self, msg: object) -> None:
        self._record(
            "obstacle_distance", scan_to_obstacle_distance(_msg_to_dict(msg))
        )

    def on_amcl(self, msg: object) -> None:
        self._record(
            "localization_confidence", amcl_to_confidence(_msg_to_dict(msg))
        )

    def on_goal_status(self, msg: object) -> None:
        statuses = _msg_to_dict(msg).get("status_list", [])
        if not statuses:
            return
        code = int(statuses[-1]["status"])
        event_type, outcome = GOAL_STATUS_TO_EVENT.get(code, (None, "success"))
        if event_type == "nav_goal_issued" and self.task_started_at is None:
            self.task_started_at = self._now()
        if event_type == "task_failed" and self.task_started_at is not None:
            self.upload_incident(outcome)
            self.task_started_at = None

    # -- incident assembly ---------------------------------------------------

    def upload_incident(self, outcome: str) -> None:
        import requests

        start = self.task_started_at or self._now() - timedelta(seconds=60)
        end = self._now()
        start_ts = start.timestamp()
        telemetry = [
            {
                "channel": channel,
                "unit": "",
                "samples": [
                    {"t": round(s["abs_t"] - start_ts, 3), "value": s["value"]}
                    for s in buf
                    if s["abs_t"] >= start_ts
                ],
            }
            for channel, buf in self.samples.items()
        ]
        incident = {
            "id": f"INC-{end:%Y%m%d-%H%M%S}-{self.robot_id}",
            "robot_id": self.robot_id,
            "robot_model": "unknown",
            "facility": self.facility,
            "task_name": "navigate_to_pose",
            "task_goal": "Nav2 navigate_to_pose goal",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "outcome": outcome,
            "severity": "error",
            "software_version": "ros2-live",
            "map_version": "unknown",
            "environment": "live capture",
            "summary": f"Live-captured {outcome} navigation task on "
                       f"{self.robot_id}",
            "events": [
                e for e in self.events
                if datetime.fromisoformat(e["timestamp"]) >= start
            ],
            "telemetry": [s for s in telemetry if s["samples"]],
        }
        response = requests.post(
            f"{self.api}/api/incidents/upload",
            files={"file": ("live.json", json.dumps(incident).encode(),
                            "application/json")},
            timeout=30,
        )
        self.get_logger().info(
            f"uploaded incident: {response.status_code} {response.text[:200]}"
        )


def _msg_to_dict(msg: object) -> dict:
    """Best-effort ROS message → dict (rosidl objects expose get_fields...)."""
    if isinstance(msg, dict):
        return msg
    from rosidl_runtime_py import message_to_ordereddict

    return json.loads(json.dumps(message_to_ordereddict(msg)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--robot-id", default="R-001")
    parser.add_argument("--facility", default="unknown")
    args = parser.parse_args()

    if rclpy is None:
        print(
            "rclpy is not available — this recorder needs a ROS 2 environment.\n"
            "BlackBox itself does not require ROS; see robotics/ros2/README.md.",
            file=sys.stderr,
        )
        return 1

    rclpy.init()
    node = BlackboxRecorder(args.api, args.robot_id, args.facility)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
