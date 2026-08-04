"""Compatibility shim — the canonical mapping now lives in the API package.

The pure ROS 2 → canonical-schema helpers moved to
``apps/api/blackbox_api/ros2_mapping.py`` so the rosbag2 (MCAP) ingestion
adapter can use them. This shim keeps ``robotics/ros2/blackbox_recorder.py``
(and any external import of ``ros2_topic_mapping``) working from a repo
checkout without installing blackbox-api.
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[2] / "apps" / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from blackbox_api.ros2_mapping import (  # noqa: E402, F401
    GOAL_STATUS_TO_EVENT,
    ROS2_TOPIC_MAPPINGS,
    TopicMapping,
    amcl_to_confidence,
    odom_to_samples,
    scan_to_obstacle_distance,
    yaw_from_quaternion,
)

__all__ = [
    "GOAL_STATUS_TO_EVENT",
    "ROS2_TOPIC_MAPPINGS",
    "TopicMapping",
    "amcl_to_confidence",
    "odom_to_samples",
    "scan_to_obstacle_distance",
    "yaw_from_quaternion",
]
