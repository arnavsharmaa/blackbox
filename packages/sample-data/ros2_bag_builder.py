"""Build a deterministic ROS 2 MCAP bag of a blocked-robot navigation run.

Used by the backend tests and scripts/make_demo_bag.py to exercise the
rosbag2 ingestion adapter without a ROS installation: the bag is written with
``mcap-ros2-support`` using the real message definitions below, exactly as
``ros2 bag record -s mcap`` would produce them.

The scripted run (all timestamps fixed, no randomness): the robot drives
+x at 0.6 m/s for 15 s, a forward obstacle appears at 12 s (clearance drops
to 0.5 m), the controller holds zero velocity from 15 s on, the Nav2
behavior tree runs three failed recoveries (Spin, BackUp, Wait) plus a
failed replan, and the navigate_to_pose goal aborts at 29 s.
"""

from __future__ import annotations

import io
import math
from types import SimpleNamespace

BAG_DURATION_S = 30.0
BAG_START_NS = 1_753_900_000_000_000_000  # fixed epoch: deterministic output

_SEP = "=" * 80

_TIME_DEF = """MSG: builtin_interfaces/Time
int32 sec
uint32 nanosec"""

_HEADER_DEF = f"""MSG: std_msgs/Header
builtin_interfaces/Time stamp
string frame_id
{_SEP}
{_TIME_DEF}"""

_GEOMETRY_DEFS = f"""MSG: geometry_msgs/PoseWithCovariance
geometry_msgs/Pose pose
float64[36] covariance
{_SEP}
MSG: geometry_msgs/Pose
geometry_msgs/Point position
geometry_msgs/Quaternion orientation
{_SEP}
MSG: geometry_msgs/Point
float64 x
float64 y
float64 z
{_SEP}
MSG: geometry_msgs/Quaternion
float64 x
float64 y
float64 z
float64 w
{_SEP}
MSG: geometry_msgs/TwistWithCovariance
geometry_msgs/Twist twist
float64[36] covariance
{_SEP}
MSG: geometry_msgs/Twist
geometry_msgs/Vector3 linear
geometry_msgs/Vector3 angular
{_SEP}
MSG: geometry_msgs/Vector3
float64 x
float64 y
float64 z"""

ODOMETRY_MSGDEF = f"""std_msgs/Header header
string child_frame_id
geometry_msgs/PoseWithCovariance pose
geometry_msgs/TwistWithCovariance twist
{_SEP}
{_HEADER_DEF}
{_SEP}
{_GEOMETRY_DEFS}"""

TWIST_MSGDEF = f"""geometry_msgs/Vector3 linear
geometry_msgs/Vector3 angular
{_SEP}
MSG: geometry_msgs/Vector3
float64 x
float64 y
float64 z"""

LASERSCAN_MSGDEF = f"""std_msgs/Header header
float32 angle_min
float32 angle_max
float32 angle_increment
float32 time_increment
float32 scan_time
float32 range_min
float32 range_max
float32[] ranges
float32[] intensities
{_SEP}
{_HEADER_DEF}"""

POSE_COV_STAMPED_MSGDEF = f"""std_msgs/Header header
geometry_msgs/PoseWithCovariance pose
{_SEP}
{_HEADER_DEF}
{_SEP}
MSG: geometry_msgs/PoseWithCovariance
geometry_msgs/Pose pose
float64[36] covariance
{_SEP}
MSG: geometry_msgs/Pose
geometry_msgs/Point position
geometry_msgs/Quaternion orientation
{_SEP}
MSG: geometry_msgs/Point
float64 x
float64 y
float64 z
{_SEP}
MSG: geometry_msgs/Quaternion
float64 x
float64 y
float64 z
float64 w"""

BEHAVIOR_TREE_LOG_MSGDEF = f"""builtin_interfaces/Time timestamp
nav2_msgs/BehaviorTreeStatusChange[] event_log
{_SEP}
MSG: nav2_msgs/BehaviorTreeStatusChange
builtin_interfaces/Time timestamp
string node_name
string previous_status
string current_status
{_SEP}
{_TIME_DEF}"""

DIAGNOSTIC_ARRAY_MSGDEF = f"""std_msgs/Header header
diagnostic_msgs/DiagnosticStatus[] status
{_SEP}
MSG: diagnostic_msgs/DiagnosticStatus
byte level
string name
string message
string hardware_id
diagnostic_msgs/KeyValue[] values
{_SEP}
MSG: diagnostic_msgs/KeyValue
string key
string value
{_SEP}
{_HEADER_DEF}"""

PATH_MSGDEF = f"""std_msgs/Header header
geometry_msgs/PoseStamped[] poses
{_SEP}
MSG: geometry_msgs/PoseStamped
std_msgs/Header header
geometry_msgs/Pose pose
{_SEP}
MSG: geometry_msgs/Pose
geometry_msgs/Point position
geometry_msgs/Quaternion orientation
{_SEP}
MSG: geometry_msgs/Point
float64 x
float64 y
float64 z
{_SEP}
MSG: geometry_msgs/Quaternion
float64 x
float64 y
float64 z
float64 w
{_SEP}
{_HEADER_DEF}"""

GOAL_STATUS_ARRAY_MSGDEF = f"""action_msgs/GoalStatus[] status_list
{_SEP}
MSG: action_msgs/GoalStatus
action_msgs/GoalInfo goal_info
int8 status
{_SEP}
MSG: action_msgs/GoalInfo
unique_identifier_msgs/UUID goal_id
builtin_interfaces/Time stamp
{_SEP}
MSG: unique_identifier_msgs/UUID
uint8[16] uuid
{_SEP}
{_TIME_DEF}"""

_ZERO36 = [0.0] * 36


def _stamp(t: float) -> dict:
    ns = BAG_START_NS + int(t * 1e9)
    return {"sec": ns // 1_000_000_000, "nanosec": ns % 1_000_000_000}


def _header(t: float, frame: str) -> dict:
    return {"stamp": _stamp(t), "frame_id": frame}


def robot_x(t: float) -> float:
    """Scripted trajectory: +x at 0.6 m/s until 15 s, stopped after."""
    return 2.0 + 0.6 * min(t, 15.0)


def commanded_speed(t: float) -> float:
    return 0.6 if t < 15.0 else 0.0


def forward_clearance(t: float) -> float:
    return 4.0 if t < 12.0 else 0.5


def build_blocked_run_bag() -> bytes:
    """Write the scripted run as an MCAP bag and return its bytes."""
    from mcap_ros2.writer import Writer

    buffer = io.BytesIO()
    writer = Writer(buffer)
    odom_schema = writer.register_msgdef("nav_msgs/msg/Odometry", ODOMETRY_MSGDEF)
    twist_schema = writer.register_msgdef("geometry_msgs/msg/Twist", TWIST_MSGDEF)
    scan_schema = writer.register_msgdef(
        "sensor_msgs/msg/LaserScan", LASERSCAN_MSGDEF
    )
    amcl_schema = writer.register_msgdef(
        "geometry_msgs/msg/PoseWithCovarianceStamped", POSE_COV_STAMPED_MSGDEF
    )
    status_schema = writer.register_msgdef(
        "action_msgs/msg/GoalStatusArray", GOAL_STATUS_ARRAY_MSGDEF
    )
    bt_schema = writer.register_msgdef(
        "nav2_msgs/msg/BehaviorTreeLog", BEHAVIOR_TREE_LOG_MSGDEF
    )
    diag_schema = writer.register_msgdef(
        "diagnostic_msgs/msg/DiagnosticArray", DIAGNOSTIC_ARRAY_MSGDEF
    )
    path_schema = writer.register_msgdef("nav_msgs/msg/Path", PATH_MSGDEF)

    def write(topic: str, schema: object, t: float, message: dict) -> None:
        ns = BAG_START_NS + int(t * 1e9)
        writer.write_message(
            topic=topic, schema=schema, message=message,
            log_time=ns, publish_time=ns,
        )

    def goal_status(t: float, code: int) -> None:
        write("/navigate_to_pose/_action/status", status_schema, t, {
            "status_list": [{
                "goal_info": {
                    "goal_id": {"uuid": [7] * 16},
                    "stamp": _stamp(t),
                },
                "status": code,
            }],
        })

    def diagnostics(t: float, statuses: list[tuple[str, int, str, str]]) -> None:
        write("/diagnostics", diag_schema, t, {
            "header": _header(t, "base_link"),
            # SimpleNamespace, not dict: mcap-ros2's serializer resolves the
            # field named "values" via hasattr first, which on a dict hits the
            # built-in .values method instead of the entry.
            "status": [
                SimpleNamespace(level=level, name=name, message=text,
                                hardware_id=hw_id, values=[])
                for name, level, text, hw_id in statuses
            ],
        })

    def bt_change(t: float, node: str, prev: str, curr: str) -> None:
        write("/behavior_tree_log", bt_schema, t, {
            "timestamp": _stamp(t),
            "event_log": [{
                "timestamp": _stamp(t),
                "node_name": node,
                "previous_status": prev,
                "current_status": curr,
            }],
        })

    goal_status(0.2, 2)  # STATUS_EXECUTING — goal accepted

    # Nav2 behavior tree: plan, follow, then three failed recoveries once the
    # obstacle blocks the path at t=12 s.
    bt_change(0.3, "ComputePathToPose", "IDLE", "RUNNING")
    bt_change(0.6, "ComputePathToPose", "RUNNING", "SUCCESS")
    bt_change(0.7, "FollowPath", "IDLE", "RUNNING")
    bt_change(14.8, "FollowPath", "RUNNING", "FAILURE")
    bt_change(15.0, "Spin", "IDLE", "RUNNING")
    bt_change(18.0, "Spin", "RUNNING", "FAILURE")
    bt_change(19.0, "BackUp", "IDLE", "RUNNING")
    bt_change(22.0, "BackUp", "RUNNING", "FAILURE")
    bt_change(23.0, "Wait", "IDLE", "RUNNING")
    bt_change(26.0, "Wait", "RUNNING", "FAILURE")
    bt_change(26.5, "ComputePathToPose", "IDLE", "RUNNING")
    bt_change(28.0, "ComputePathToPose", "RUNNING", "FAILURE")

    # Global plan published at t=0.8: straight line to the goal at x=13.4.
    write("/plan", path_schema, 0.8, {
        "header": _header(0.8, "map"),
        "poses": [
            {
                "header": _header(0.8, "map"),
                "pose": {
                    "position": {"x": 2.0 + 0.6 * step, "y": 3.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            }
            for step in range(20)  # last pose: x = 13.4 (the goal)
        ],
    })

    # 1 Hz diagnostics; the drive controller trips a WARN while blocked.
    for tick in range(int(BAG_DURATION_S)):
        warn = 20 <= tick
        diagnostics(float(tick), [
            ("drive_controller: Motor state",
             1 if warn else 0,
             "Motor temperature high" if warn else "OK",
             "roboteq_sbl2360"),
            ("lidar_front: Scan rate", 0, "OK", "sick_tim781"),
        ])

    steps = int(BAG_DURATION_S / 0.2)
    for i in range(steps + 1):
        t = round(i * 0.2, 3)
        speed = commanded_speed(t)

        write("/odom", odom_schema, t, {
            "header": _header(t, "odom"),
            "child_frame_id": "base_link",
            "pose": {
                "pose": {
                    "position": {"x": robot_x(t), "y": 3.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "covariance": _ZERO36,
            },
            "twist": {
                "twist": {
                    "linear": {"x": speed, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
                "covariance": _ZERO36,
            },
        })

        if i % 5 == 0:  # 1 Hz commands
            write("/cmd_vel", twist_schema, t, {
                "linear": {"x": speed, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
            })

        if i % 2 == 0:  # ~2.5 Hz scans, 5 beams across ±30°
            clearance = forward_clearance(t)
            write("/scan", scan_schema, t, {
                "header": _header(t, "laser"),
                "angle_min": -math.pi / 6,
                "angle_max": math.pi / 6,
                "angle_increment": math.pi / 12,
                "time_increment": 0.0,
                "scan_time": 0.4,
                "range_min": 0.05,
                "range_max": 12.0,
                "ranges": [clearance + 0.4, clearance + 0.1, clearance,
                           clearance + 0.1, clearance + 0.4],
                "intensities": [],
            })

        if i % 5 == 0:  # 1 Hz AMCL pose, tight covariance -> high confidence
            write("/amcl_pose", amcl_schema, t, {
                "header": _header(t, "map"),
                "pose": {
                    "pose": {
                        "position": {"x": robot_x(t), "y": 3.0, "z": 0.0},
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0,
                                        "w": 1.0},
                    },
                    "covariance": [0.004 if j in (0, 7, 35) else 0.0
                                   for j in range(36)],
                },
            })

    goal_status(29.0, 6)  # STATUS_ABORTED — no path around the obstacle

    writer.finish()
    return buffer.getvalue()


def build_stale_lidar_bag() -> bytes:
    """A short run whose front lidar diagnostics go STALE at t=2 s."""
    from mcap_ros2.writer import Writer

    buffer = io.BytesIO()
    writer = Writer(buffer)
    diag_schema = writer.register_msgdef(
        "diagnostic_msgs/msg/DiagnosticArray", DIAGNOSTIC_ARRAY_MSGDEF
    )
    odom_schema = writer.register_msgdef("nav_msgs/msg/Odometry", ODOMETRY_MSGDEF)

    def write(topic: str, schema: object, t: float, message: dict) -> None:
        ns = BAG_START_NS + int(t * 1e9)
        writer.write_message(
            topic=topic, schema=schema, message=message,
            log_time=ns, publish_time=ns,
        )

    for tick in range(6):
        t = float(tick)
        write("/odom", odom_schema, t, {
            "header": _header(t, "odom"),
            "child_frame_id": "base_link",
            "pose": {
                "pose": {
                    "position": {"x": 1.0 + 0.2 * t, "y": 0.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
                "covariance": _ZERO36,
            },
            "twist": {
                "twist": {
                    "linear": {"x": 0.2, "y": 0.0, "z": 0.0},
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
                "covariance": _ZERO36,
            },
        })
        stale = t >= 2.0
        write("/diagnostics", diag_schema, t, {
            "header": _header(t, "base_link"),
            # SimpleNamespace for the same .values-shadowing reason as above.
            "status": [SimpleNamespace(
                level=3 if stale else 0,
                name="lidar_front: Scan timestamps",
                message="Scan data is stale" if stale else "OK",
                hardware_id="sick_tim781",
                values=[],
            )],
        })

    writer.finish()
    return buffer.getvalue()
