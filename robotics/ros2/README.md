# ROS 2 integration

ROS 2 is **not** required to run BlackBox — the primary app runs entirely on
seeded/normalized data. This directory documents the path from a live Nav2
robot (or a rosbag2 recording) into BlackBox.

## Live recorder node

[`blackbox_recorder.py`](./blackbox_recorder.py) is a minimal `rclpy` node
that:

1. subscribes to the topics in the
   [adapter mapping](../adapters/README.md#ros-2-topic-mapping),
2. keeps a rolling in-memory buffer of canonical telemetry samples and events
   (converted with the pure helpers in
   `robotics/adapters/ros2_topic_mapping.py`),
3. on a terminal `navigate_to_pose` status (aborted/canceled), assembles a
   canonical incident JSON and POSTs it to `/api/incidents/upload`.

Run it inside any ROS 2 Humble+ environment that has a Nav2 stack running:

```bash
pip install requests            # the only non-ROS dependency
python3 robotics/ros2/blackbox_recorder.py --api http://localhost:8000 \
    --robot-id W-104 --facility "Warehouse 3"
```

The node degrades gracefully: if `rclpy` is not importable it prints an
explanation and exits instead of crashing, so it is safe to keep in the repo
without ROS installed.

## Offline rosbag2 ingestion

For post-hoc analysis, record with:

```bash
ros2 bag record /odom /cmd_vel /scan /amcl_pose \
    /navigate_to_pose/_action/status /behavior_tree_log /diagnostics
```

Record with MCAP storage (`-s mcap`, the default on recent distros), then
upload the `.mcap` file directly — the rosbag2 adapter is implemented:

```bash
curl -X POST http://localhost:8000/api/incidents/upload \
  -F "file=@rosbag2_.../rosbag2_..._0.mcap" \
  -F 'metadata={"id": "INC-BAG-001", "robot_id": "W-104"}'
```

No ROS installation is needed on the BlackBox side. To try the path without a
robot, `make demo-bag` generates a deterministic sample bag and prints the
upload command. See
[`../adapters/README.md`](../adapters/README.md#how-the-rosbag2-adapter-works)
for supported topics and remaining work.
