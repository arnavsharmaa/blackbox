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

## ROS 2 topic mapping

A future `Rosbag2Adapter` should map common Nav2-stack topics onto the
canonical schema like this. `ros2_topic_mapping.py` in this directory encodes
the same table as data plus pure conversion helpers you can unit-test without
ROS installed.

| ROS 2 topic | Message type | Canonical target |
| --- | --- | --- |
| `/odom` | `nav_msgs/Odometry` | `pos_x`, `pos_y`, `heading`, `linear_velocity`, `angular_velocity` telemetry + periodic `pose_updated` events |
| `/cmd_vel` | `geometry_msgs/Twist` | `velocity_command` events (`payload.linear`, `payload.angular`) |
| `/scan` | `sensor_msgs/LaserScan` | `obstacle_distance` telemetry (min range in the forward arc) + `obstacle_distance_updated` events; scan gaps become sensor-staleness warnings |
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | `localization_confidence` telemetry (mapped from covariance trace) |
| `/navigate_to_pose/_action/status` | `action_msgs/GoalStatusArray` | `nav_goal_issued`, `task_timed_out`, `task_failed` events; `goal_distance` derived from the active goal pose |
| `/behavior_tree_log` | `nav2_msgs/BehaviorTreeLog` | `planner_state_changed`, `recovery_started`, `recovery_completed` events + `planner_state` / `recovery_count` telemetry |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | `warning_raised` / `error_raised` events with `evidence_tags` from hardware IDs |

### Practical rosbag2 ingestion plan

1. Read the bag with `rosbag2_py.SequentialReader` (or `mcap` directly) —
   offline, no ROS graph needed.
2. Slice the bag around the failure: from `task_started` (first accepted
   `navigate_to_pose` goal) to terminal goal status, plus a configurable
   pre-roll.
3. Downsample continuous topics to ~5 Hz into telemetry samples with
   `t = stamp - start_stamp`.
4. Emit events per the table above; carry the raw message (as a dict) in
   `payload` for the event inspector.
5. Validate through `Incident.model_validate` and POST the JSON to
   `/api/incidents/upload` — nothing else in BlackBox needs to know the data
   came from a bag.

See [`../ros2/README.md`](../ros2/README.md) for the live recorder-node
example.
