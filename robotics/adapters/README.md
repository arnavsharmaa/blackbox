# BlackBox ingestion adapters

Every ingestion path converts an external recording into the canonical
`Incident` schema (`apps/api/blackbox_api/schemas/incident.py`) by
implementing `IncidentAdapter`:

```python
from blackbox_api.ingestion.base import IncidentAdapter, IngestError
from blackbox_api.schemas import Incident

class MyAdapter(IncidentAdapter):
    name = "my-format"
    extensions = (".myext",)

    def parse(self, raw: bytes, *, metadata=None) -> Incident:
        ...  # raise IngestError with field-level details on bad input
```

Adapters are pure functions from bytes to a validated `Incident`; persistence
and analysis happen in `blackbox_api.ingestion.service`. To register a new
adapter, add an instance to `ADAPTERS` in that module — upload routing by file
extension and error handling come for free.

## Built-in adapters

| Adapter | Extensions | Notes |
| --- | --- | --- |
| `JsonIncidentAdapter` | `.json` | Full canonical incident document |
| `CsvIncidentAdapter` | `.csv` | Normalized event stream + metadata JSON (see [`normalized-events.example.csv`](../sample-incidents/normalized-events.example.csv)) |
| `Rosbag2Adapter` | `.mcap` | ROS 2 bags in MCAP format (`ros2 bag record -s mcap`); decoded with pure-Python `mcap-ros2-support`, no ROS install needed. Requires metadata with at least `id` and `robot_id`. Try it: `make demo-bag`. |

## ROS 2 topic mapping

`Rosbag2Adapter` maps common Nav2-stack topics onto the canonical schema as
below. The pure conversion helpers live in
`apps/api/blackbox_api/ros2_mapping.py` (stdlib-only, unit-testable without
ROS); `ros2_topic_mapping.py` in this directory is a compatibility shim that
re-exports them for the live recorder node.

| ROS 2 topic | Message type | Canonical target |
| --- | --- | --- |
| `/odom` | `nav_msgs/Odometry` | `pos_x`, `pos_y`, `heading`, `linear_velocity`, `angular_velocity` telemetry + periodic `pose_updated` events |
| `/cmd_vel` | `geometry_msgs/Twist` | `velocity_command` events (`payload.linear`, `payload.angular`) |
| `/scan` | `sensor_msgs/LaserScan` | `obstacle_distance` telemetry (min range in the forward arc) + `obstacle_distance_updated` events; scan gaps become sensor-staleness warnings |
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | `localization_confidence` telemetry (mapped from covariance trace) |
| `/navigate_to_pose/_action/status` | `action_msgs/GoalStatusArray` | `nav_goal_issued`, `task_timed_out`, `task_failed` events; `goal_distance` derived from the active goal pose |
| `/behavior_tree_log` | `nav2_msgs/BehaviorTreeLog` | `planner_state_changed`, `recovery_started`, `recovery_completed` events + `planner_state` / `recovery_count` telemetry |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | `warning_raised` / `error_raised` events with `evidence_tags` from hardware IDs |

### How the rosbag2 adapter works

`blackbox_api/ingestion/rosbag2_adapter.py` reads the MCAP container with
`mcap` + `mcap-ros2-support` (CDR decoding via the message definitions
embedded in the bag — offline, no ROS graph needed), downsamples continuous
topics to replay-friendly rates, derives the outcome from the terminal
`navigate_to_pose` goal status, and validates the result through
`Incident.model_validate` like every other adapter. Supported topics today:
`/odom`, `/cmd_vel`, `/scan`, `/amcl_pose`,
`/navigate_to_pose/_action/status`. Remaining work: `/behavior_tree_log`
(recovery events), `/diagnostics` (sensor-staleness warnings), goal-distance
derivation from the goal pose, and the sqlite3 (`.db3`) storage plugin.

See [`../ros2/README.md`](../ros2/README.md) for the live recorder-node
example.
