#!/usr/bin/env python3
"""Example ROS 2 node that live-streams to BlackBox over WebSocket.

Converts Nav2 topics to canonical events/samples and streams them to
``/api/stream/{robot_id}``; the server keeps the rolling pre-failure
buffer and cuts an analyzed incident the moment a task fails, so the
node holds no incident state of its own.

Requires a ROS 2 environment (rclpy + Nav2 message packages) and the
``websockets`` package. Outside ROS this file only documents the
integration — it exits with a clear message instead of crashing. See
robotics/ros2/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import datetime, timezone
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

try:
    from websockets.sync.client import connect as ws_connect
except ImportError:
    ws_connect = None

#: Per-channel downsampling: at most one sample per period.
SAMPLE_PERIOD_S = 0.2


class BlackboxStreamer(Node):  # type: ignore[misc]
    """Thin streaming client: topics in, WebSocket frames out."""

    def __init__(self, ws_url: str, robot_id: str, facility: str) -> None:
        super().__init__("blackbox_recorder")
        self.ws = ws_connect(ws_url)
        ready = json.loads(self.ws.recv())
        self.get_logger().info(
            f"streaming to BlackBox (server window {ready.get('window_s')} s)"
        )
        self._send({
            "type": "hello",
            "meta": {
                "facility": facility,
                "task_name": "navigate_to_pose",
                "task_goal": "Nav2 navigate_to_pose goal",
                "software_version": "ros2-live",
                "environment": "live capture",
            },
        })
        self._lock = threading.Lock()
        self._last_sample: dict[str, float] = {}
        threading.Thread(target=self._read_replies, daemon=True).start()

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

    def _read_replies(self) -> None:
        """Log incident/error frames the server pushes back."""
        for raw in self.ws:
            frame = json.loads(raw)
            if frame.get("type") == "incident":
                self.get_logger().info(
                    f"BlackBox cut incident {frame['incident_id']}: "
                    f"{frame['failure_category']} "
                    f"({frame['confidence']:.0%} confidence)"
                )
            elif frame.get("type") == "error":
                self.get_logger().warning(f"BlackBox: {frame['detail']}")

    def _now(self) -> float:
        return datetime.now(timezone.utc).timestamp()

    def _send(self, frame: dict) -> None:
        with self._lock:
            self.ws.send(json.dumps(frame))

    def _sample(self, channel: str, value: float) -> None:
        t = self._now()
        if t - self._last_sample.get(channel, 0.0) < SAMPLE_PERIOD_S:
            return
        self._last_sample[channel] = t
        self._send({
            "type": "sample", "t": t, "channel": channel,
            "value": round(float(value), 4),
        })

    def _event(self, event_type: str, subsystem: str, message: str,
               severity: str = "info", payload: dict | None = None) -> None:
        self._send({
            "type": "event", "t": self._now(), "event_type": event_type,
            "subsystem": subsystem, "severity": severity,
            "message": message, "payload": payload or {},
        })

    # -- topic handlers convert with the pure mapping helpers ----------------

    def on_odom(self, msg: object) -> None:
        for channel, value in odom_to_samples(_msg_to_dict(msg)).items():
            self._sample(channel, value)

    def on_cmd_vel(self, msg: object) -> None:
        data = _msg_to_dict(msg)
        self._event(
            "velocity_command", "controller", "cmd_vel from /cmd_vel",
            payload={
                "linear": data["linear"]["x"],
                "angular": data["angular"]["z"],
            },
        )

    def on_scan(self, msg: object) -> None:
        self._sample(
            "obstacle_distance", scan_to_obstacle_distance(_msg_to_dict(msg))
        )

    def on_amcl(self, msg: object) -> None:
        self._sample(
            "localization_confidence", amcl_to_confidence(_msg_to_dict(msg))
        )

    def on_goal_status(self, msg: object) -> None:
        statuses = _msg_to_dict(msg).get("status_list", [])
        if not statuses:
            return
        code = int(statuses[-1]["status"])
        event_type, _outcome = GOAL_STATUS_TO_EVENT.get(code, (None, ""))
        if event_type is None:
            return
        severity = "critical" if event_type == "task_failed" else "info"
        # A terminal event makes the server cut and analyze the incident.
        self._event(
            event_type, "navigation",
            f"Nav2 goal status {code}", severity=severity,
            payload={"goal_status": code},
        )


def _msg_to_dict(msg: object) -> dict:
    """Best-effort ROS message → dict (rosidl objects expose get_fields...)."""
    if isinstance(msg, dict):
        return msg
    from rosidl_runtime_py import message_to_ordereddict

    return json.loads(json.dumps(message_to_ordereddict(msg)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="ws://localhost:8000",
                        help="BlackBox WebSocket origin (ws:// or wss://)")
    parser.add_argument("--robot-id", default="R-001")
    parser.add_argument("--facility", default="unknown")
    parser.add_argument("--token", default=None,
                        help="API token when BLACKBOX_API_TOKENS is set")
    args = parser.parse_args()

    if rclpy is None:
        print(
            "rclpy is not available — this recorder needs a ROS 2 environment.\n"
            "BlackBox itself does not require ROS; see robotics/ros2/README.md.",
            file=sys.stderr,
        )
        return 1
    if ws_connect is None:
        print("pip install websockets to use the streaming recorder.",
              file=sys.stderr)
        return 1

    url = f"{args.api}/api/stream/{args.robot_id}"
    if args.token:
        url += f"?token={args.token}"

    rclpy.init()
    node = BlackboxStreamer(url, args.robot_id, args.facility)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.ws.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
