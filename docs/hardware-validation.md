# Validating BlackBox against a real Nav2 bag

BlackBox's rosbag2 ingestion has been proven against deterministic
synthetic bags. This guide produces a *real* failure recording — from a
Nav2 stack driving a simulated robot — and runs it through the pipeline.
No hardware required: Gazebo + TurtleBot3 works end-to-end. If you have a
physical robot, every step from "record" onward is identical.

If you'd rather test the pipeline without any ROS installation at all,
`make demo-bag` writes a synthetic MCAP bag and prints the upload command.

## Prerequisites

- ROS 2 (Humble or newer) with Nav2 and the TurtleBot3 packages:

```bash
sudo apt install ros-$ROS_DISTRO-navigation2 ros-$ROS_DISTRO-nav2-bringup \
  ros-$ROS_DISTRO-turtlebot3-gazebo ros-$ROS_DISTRO-rosbag2-storage-mcap
```

- BlackBox running (`make demo`, or Docker) on a machine that can receive
  the bag file. ROS and BlackBox do **not** need to be on the same machine.

## 1. Launch the simulation

```bash
export TURTLEBOT3_MODEL=waffle
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False
```

This brings up Gazebo, Nav2, and RViz with the TurtleBot3 world. Set the
initial pose in RViz (2D Pose Estimate) so AMCL converges.

## 2. Start recording — before sending the goal

```bash
ros2 bag record -s mcap -o blocked_run \
  /odom /cmd_vel /scan /amcl_pose /plan \
  /navigate_to_pose/_action/status /behavior_tree_log /diagnostics
```

Notes:

- `-s mcap` matters: BlackBox reads the MCAP storage format. The default
  sqlite3 (`.db3`) format is not yet supported (sqlite3 bags don't embed
  message definitions the way MCAP does).
- Any subset of these topics works — each one you include adds telemetry
  channels or events to the reconstruction. `/behavior_tree_log` is what
  turns recovery behaviors into first-class evidence, and `/plan` is how
  the goal position (and therefore `goal_distance`) is derived.

## 3. Cause a failure

The classic persistent-obstacle scenario:

1. In Gazebo, drop an object (a cube or cylinder from the insert palette)
   across a doorway or corridor.
2. In RViz, send a **Nav2 Goal** to a point on the far side of the
   blockage.
3. Watch the robot approach, fail to find a way through, run its recovery
   behaviors (spin, backup, wait), and eventually abort the goal.

Let the goal reach a terminal state — BlackBox derives the incident
outcome from the last `/navigate_to_pose/_action/status` message
(aborted → `failed`, canceled → `aborted`, succeeded → `success`).

## 4. Stop recording and upload

Stop the recorder (Ctrl-C). The bag is at
`blocked_run/blocked_run_0.mcap`.

Upload it on the **Upload** page, with minimal metadata:

```json
{"id": "INC-TB3-BLOCKED-001", "robot_id": "tb3-sim"}
```

or from the shell:

```bash
curl -X POST http://localhost:8000/api/incidents/upload \
  -F "file=@blocked_run/blocked_run_0.mcap" \
  -F 'metadata={"id": "INC-TB3-BLOCKED-001", "robot_id": "tb3-sim"}'
```

The metadata object accepts any incident field as an override
(`robot_model`, `facility`, `task_name`, `severity`, …); `id` and
`robot_id` are the only required ones.

## 5. Judge the result

Open the new incident and check:

- **Diagnosis** — did it call the blockage a persistent obstacle? With
  what confidence? Would an engineer agree? Use the **Confirm / Correct**
  buttons on the incident page — verdicts feed the measured-precision
  table in fleet analytics.
- **Replay** — does the path map match what you watched in Gazebo? Do the
  velocity and obstacle-distance traces make sense?
- **Events** — are the recovery behaviors there (from
  `/behavior_tree_log`)? Warnings for the clearance drop?
- **Compare** — if you also record a clean run of the same goal, upload
  it and use the Compare view: the first-divergence marker should land
  where the obstacle first entered sensor range.

## 6. Report what you found

Open a
[bag validation report](https://github.com/arnavsharmaa/blackbox/issues/new?template=bag-validation.md)
with the diagnosis, what it got right or wrong, and (if you can share it)
the bag. Wrong diagnoses are *more* valuable than right ones — each one
is a rule or threshold improvement waiting to happen. Thresholds can be
tuned per deployment with `BLACKBOX_RULE_*` variables without touching
code; genuinely new failure modes can be prototyped as
`BLACKBOX_EXTRA_RULES` plug-ins.

## Known limitations

- **MCAP only** — record with `-s mcap`, or convert an existing `.db3`
  bag with `ros2 bag convert`.
- **Action feedback messages** (`NavigateToPose_FeedbackMessage`) can't
  be decoded by the pure-Python reader BlackBox uses, so `goal_distance`
  is derived from the `/plan` path and odometry instead of the action
  feedback. In practice the derived value tracks the real one closely.
- **Clock**: incident timestamps come from bag message log-times. Sim
  time in Gazebo is fine; mixed clock sources on a real robot may skew
  event ordering slightly.
