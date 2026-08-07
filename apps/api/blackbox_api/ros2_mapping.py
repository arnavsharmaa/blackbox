"""ROS 2 → BlackBox canonical-schema mapping.

Pure data + conversion helpers with no ROS dependency (stdlib only — this
module deliberately avoids importing the rest of blackbox_api so the live
recorder node in robotics/ros2/ can use it inside a ROS environment). Used by
the rosbag2 (MCAP) ingestion adapter and the recorder node. Message payloads
are plain dicts shaped like their ROS counterparts.
"""

from __future__ import annotations

import math
from typing import Any, TypedDict


class TopicMapping(TypedDict):
    msg_type: str
    telemetry_channels: list[str]
    event_types: list[str]


#: The canonical topic table. Keep in sync with robotics/adapters/README.md.
ROS2_TOPIC_MAPPINGS: dict[str, TopicMapping] = {
    "/odom": {
        "msg_type": "nav_msgs/msg/Odometry",
        "telemetry_channels": [
            "pos_x", "pos_y", "heading", "linear_velocity", "angular_velocity",
        ],
        "event_types": ["pose_updated"],
    },
    "/cmd_vel": {
        "msg_type": "geometry_msgs/msg/Twist",
        "telemetry_channels": [],
        "event_types": ["velocity_command"],
    },
    "/scan": {
        "msg_type": "sensor_msgs/msg/LaserScan",
        "telemetry_channels": ["obstacle_distance"],
        "event_types": ["obstacle_distance_updated", "warning_raised"],
    },
    "/amcl_pose": {
        "msg_type": "geometry_msgs/msg/PoseWithCovarianceStamped",
        "telemetry_channels": ["localization_confidence"],
        "event_types": [],
    },
    "/navigate_to_pose/_action/status": {
        "msg_type": "action_msgs/msg/GoalStatusArray",
        "telemetry_channels": ["goal_distance"],
        "event_types": ["nav_goal_issued", "task_timed_out", "task_failed"],
    },
    "/behavior_tree_log": {
        "msg_type": "nav2_msgs/msg/BehaviorTreeLog",
        "telemetry_channels": ["planner_state", "recovery_count"],
        "event_types": [
            "planner_state_changed", "recovery_started", "recovery_completed",
        ],
    },
    "/diagnostics": {
        "msg_type": "diagnostic_msgs/msg/DiagnosticArray",
        "telemetry_channels": [],
        "event_types": ["warning_raised", "error_raised"],
    },
}


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    """Planar heading (yaw, radians) from a quaternion."""
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def odom_to_samples(msg: dict[str, Any]) -> dict[str, float]:
    """nav_msgs/Odometry (as dict) → one sample per motion channel."""
    position = msg["pose"]["pose"]["position"]
    orientation = msg["pose"]["pose"]["orientation"]
    twist = msg["twist"]["twist"]
    return {
        "pos_x": float(position["x"]),
        "pos_y": float(position["y"]),
        "heading": yaw_from_quaternion(
            orientation["x"], orientation["y"],
            orientation["z"], orientation["w"],
        ),
        "linear_velocity": float(twist["linear"]["x"]),
        "angular_velocity": float(twist["angular"]["z"]),
    }


def scan_to_obstacle_distance(
    msg: dict[str, Any], forward_arc_rad: float = math.pi / 3
) -> float:
    """sensor_msgs/LaserScan (as dict) → min clearance in the forward arc."""
    angle = float(msg["angle_min"])
    increment = float(msg["angle_increment"])
    range_max = float(msg["range_max"])
    best = range_max
    for reading in msg["ranges"]:
        if abs(angle) <= forward_arc_rad / 2:
            value = float(reading)
            if math.isfinite(value) and 0.0 < value < best:
                best = value
        angle += increment
    return best


def amcl_to_confidence(msg: dict[str, Any], scale: float = 0.5) -> float:
    """PoseWithCovarianceStamped (as dict) → [0, 1] confidence.

    Maps the x/y/yaw covariance trace through exp(-trace/scale): a tight
    filter (trace ≈ 0.01) reads ≈ 0.98, a diverged one (trace ≥ 2) reads
    ≈ 0. Tune ``scale`` per robot.
    """
    covariance = msg["pose"]["covariance"]
    trace = float(covariance[0]) + float(covariance[7]) + float(covariance[35])
    return max(0.0, min(1.0, math.exp(-trace / scale)))


#: nav2 GoalStatus codes → (canonical event type or None, incident outcome).
GOAL_STATUS_TO_EVENT: dict[int, tuple[str | None, str]] = {
    2: ("nav_goal_issued", "success"),   # STATUS_EXECUTING
    4: (None, "success"),                # STATUS_SUCCEEDED
    5: ("task_failed", "aborted"),       # STATUS_CANCELED
    6: ("task_failed", "failed"),        # STATUS_ABORTED
}


#: Nav2 behavior-tree node names that implement recovery behaviors.
RECOVERY_BT_NODES: frozenset[str] = frozenset({
    "Spin",
    "BackUp",
    "Wait",
    "DriveOnHeading",
    "ClearLocalCostmap",
    "ClearGlobalCostmap",
    "ClearEntireCostmap",
})

#: Nav2 behavior-tree node names → canonical planner state while RUNNING.
BT_NODE_TO_PLANNER_STATE: dict[str, str] = {
    "ComputePathToPose": "planning",
    "FollowPath": "executing",
    "NavigateRecovery": "recovering",
}


def bt_status_changes(
    msg: dict[str, Any],
) -> list[tuple[int, str, str, str]]:
    """nav2_msgs/BehaviorTreeLog (as dict) → (t_ns, node, prev, current).

    Each BehaviorTreeStatusChange carries its own stamp; entries missing one
    fall back to the log-level timestamp.
    """

    def to_ns(stamp: dict[str, Any] | None) -> int | None:
        if not stamp:
            return None
        return int(stamp["sec"]) * 1_000_000_000 + int(stamp["nanosec"])

    log_ns = to_ns(msg.get("timestamp")) or 0
    changes: list[tuple[int, str, str, str]] = []
    for entry in msg.get("event_log") or []:
        t_ns = to_ns(entry.get("timestamp")) or log_ns
        changes.append((
            t_ns,
            str(entry.get("node_name", "")),
            str(entry.get("previous_status", "")),
            str(entry.get("current_status", "")),
        ))
    return changes
