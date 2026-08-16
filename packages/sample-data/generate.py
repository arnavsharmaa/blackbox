#!/usr/bin/env python3
"""Deterministic sample-incident generator for BlackBox.

Produces four fully deterministic incidents (fixed timestamps, no randomness),
each designed to trigger a different rule in the analysis engine:

    1. INC-2026-0728-001  persistent obstacle -> navigation timeout   (primary)
    2. INC-2026-0729-002  localization confidence collapse
    3. INC-2026-0730-003  controller oscillation in a narrow doorway
    4. INC-2026-0731-004  lidar / obstacle-sensor dropout

Run:  python generate.py            (writes JSON files into ./incidents/)

Stdlib-only on purpose: the canonical schema validation happens when the files
are ingested (scripts/seed.py and the backend test suite both validate them
against blackbox_api.schemas.Incident).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).parent / "incidents"

Keyframes = list[tuple[float, float]]


def interp(keys: Keyframes, t: float) -> float:
    """Piecewise-linear interpolation over (time, value) keyframes."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            if t1 == t0:
                return v1
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def iso(base: datetime, t: float) -> str:
    return (base + timedelta(seconds=t)).isoformat().replace("+00:00", "Z")


def sample_times(duration: float, dt: float) -> list[float]:
    n = int(round(duration / dt))
    return [round(i * dt, 3) for i in range(n + 1)]


def series(channel: str, unit: str, samples: list[tuple[float, Any]]) -> dict:
    return {
        "channel": channel,
        "unit": unit,
        "samples": [{"t": t, "value": v} for t, v in samples],
    }


def event(
    base: datetime,
    t: float,
    event_type: str,
    subsystem: str,
    message: str,
    severity: str = "info",
    payload: dict | None = None,
    correlation_id: str | None = None,
    evidence_tags: list[str] | None = None,
) -> dict:
    return {
        "timestamp": iso(base, t),
        "event_type": event_type,
        "subsystem": subsystem,
        "severity": severity,
        "message": message,
        "payload": payload or {},
        "correlation_id": correlation_id,
        "evidence_tags": evidence_tags or [],
    }


def motion_series(
    times: list[float],
    x_keys: Keyframes,
    y_keys: Keyframes,
    h_keys: Keyframes,
) -> tuple[list, list, list, list, list]:
    """Derive pos/heading/velocity samples from keyframed trajectories."""
    xs, ys, hs, lin, ang = [], [], [], [], []
    for i, t in enumerate(times):
        x, y, h = interp(x_keys, t), interp(y_keys, t), interp(h_keys, t)
        xs.append((t, round(x, 4)))
        ys.append((t, round(y, 4)))
        hs.append((t, round(h, 4)))
        if i == 0:
            lin.append((t, 0.0))
            ang.append((t, 0.0))
        else:
            dt = t - times[i - 1]
            dx = x - interp(x_keys, times[i - 1])
            dy = y - interp(y_keys, times[i - 1])
            dh = h - interp(h_keys, times[i - 1])
            lin.append((t, round(math.hypot(dx, dy) / dt, 4)))
            ang.append((t, round(dh / dt, 4)))
    return xs, ys, hs, lin, ang


def dist_to(xs: Keyframes, ys: Keyframes, t: float, px: float, py: float) -> float:
    return math.hypot(interp(xs, t) - px, interp(ys, t) - py)


# ---------------------------------------------------------------------------
# Incident 1 — persistent obstacle causing navigation timeout (primary demo)
# ---------------------------------------------------------------------------


def incident_obstacle() -> dict:
    base = datetime(2026, 7, 28, 9, 14, 3, tzinfo=timezone.utc)
    duration, dt = 92.0, 0.2
    times = sample_times(duration, dt)
    goal = (18.0, 6.5)
    obstacle = (13.5, 5.35)
    corr = "TASK-4821"

    x_keys = [
        (0, 2.0), (2, 2.8), (12, 10.0), (16, 11.6), (26, 13.0), (30, 13.2),
        (34, 13.25), (52, 13.25), (58, 13.05), (62, 13.05), (66, 13.22),
        (92, 13.22),
    ]
    y_keys = [
        (0, 2.0), (12, 2.0), (16, 3.0), (26, 4.8), (30, 5.0), (34, 5.03),
        (52, 5.03), (58, 4.85), (62, 4.85), (66, 5.0), (92, 5.0),
    ]
    h_keys = [
        (0, 0.0), (12, 0.0), (16, 0.55), (24, 0.85), (40, 0.85), (43, 1.9),
        (46, 0.85), (92, 0.85),
    ]

    xs, ys, hs, lin, ang = motion_series(times, x_keys, y_keys, h_keys)

    def obstacle_distance(t: float) -> float:
        if t < 20:
            # Nothing in the corridor: sensor reports near max range.
            return round(4.9 + 0.08 * math.sin(0.7 * t), 3)
        return round(min(5.0, dist_to(x_keys, y_keys, t, *obstacle)), 3)

    obs = [(t, obstacle_distance(t)) for t in times]
    goal_dist = [
        (t, round(dist_to(x_keys, y_keys, t, *goal), 3)) for t in times
    ]
    loc = [(t, round(0.97 + 0.015 * math.sin(0.15 * t), 4)) for t in times]
    battery = [(t, round(93.0 - 0.012 * t, 3)) for t in times]

    planner_states = [
        (0.0, "idle"), (0.8, "planning"), (1.5, "executing"),
        (30.0, "avoiding"), (40.0, "recovering"), (60.0, "replanning"),
        (61.5, "avoiding"), (90.0, "failed"),
    ]
    recovery_counts = [(0.0, 0), (40.0, 1), (52.0, 2), (64.0, 3)]

    events: list[dict] = [
        event(base, 0.0, "task_started", "task_manager",
              "Task 'Deliver pallet to Loading Bay B' started",
              payload={"task": "deliver_pallet", "destination": "Loading Bay B"},
              correlation_id=corr),
        event(base, 0.5, "nav_goal_issued", "navigation",
              "Navigation goal issued: Loading Bay B (18.00, 6.50)",
              payload={"goal_x": goal[0], "goal_y": goal[1],
                       "frame": "map", "tolerance_m": 0.25},
              correlation_id=corr),
        event(base, 0.8, "planner_state_changed", "planner",
              "Planner state: planning", payload={"state": "planning"},
              correlation_id=corr),
        event(base, 1.5, "planner_state_changed", "planner",
              "Planner state: executing (global path 17.4 m)",
              payload={"state": "executing", "path_length_m": 17.4},
              correlation_id=corr),
    ]

    # Normal driving: velocity commands every 2 s, pose updates every 5 s.
    for t in [round(v, 1) for v in frange(2.0, 28.0, 2.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            f"cmd_vel linear={interp_val(lin, t):.2f} m/s "
            f"angular={interp_val(ang, t):.2f} rad/s",
            payload={"linear": interp_val(lin, t), "angular": interp_val(ang, t)},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(5.0, 90.0, 5.0)]:
        events.append(event(
            base, t, "pose_updated", "localization",
            f"Pose ({interp(x_keys, t):.2f}, {interp(y_keys, t):.2f}) "
            f"θ={interp(h_keys, t):.2f}",
            payload={"x": round(interp(x_keys, t), 3),
                     "y": round(interp(y_keys, t), 3),
                     "heading": round(interp(h_keys, t), 3),
                     "covariance_trace": 0.014},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(20.0, 90.0, 4.0)]:
        events.append(event(
            base, t, "obstacle_distance_updated", "perception",
            f"Nearest obstacle {obstacle_distance(t):.2f} m",
            payload={"distance_m": obstacle_distance(t),
                     "bearing_rad": 0.82, "source": "lidar_front"},
            correlation_id=corr))

    events += [
        event(base, 26.0, "warning_raised", "perception",
              "Obstacle detected 1.9 m ahead in path corridor",
              severity="warning",
              payload={"distance_m": 1.9, "classification": "unclassified_static",
                       "obstacle_x": 13.5, "obstacle_y": 5.35},
              correlation_id=corr, evidence_tags=["obstacle"]),
        event(base, 30.0, "planner_state_changed", "planner",
              "Planner state: avoiding — no collision-free local trajectory",
              severity="warning", payload={"state": "avoiding"},
              correlation_id=corr, evidence_tags=["planner", "obstacle"]),
        event(base, 32.0, "warning_raised", "planner",
              "Obstacle distance 0.52 m below safety threshold 0.60 m",
              severity="warning",
              payload={"distance_m": 0.52, "threshold_m": 0.6},
              correlation_id=corr,
              evidence_tags=["obstacle", "safety_threshold"]),
    ]

    # The controller holds a zero-velocity command while blocked.
    for t in [round(v, 1) for v in frange(31.0, 40.0, 1.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            "cmd_vel linear=0.00 m/s angular=0.00 rad/s (blocked)",
            payload={"linear": 0.0, "angular": 0.0},
            correlation_id=corr, evidence_tags=["zero_velocity"]))

    events += [
        event(base, 40.0, "recovery_started", "planner",
              "Recovery behavior started: rotate_in_place",
              severity="warning", payload={"behavior": "rotate_in_place",
                                           "attempt": 1},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 46.0, "recovery_completed", "planner",
              "Recovery rotate_in_place completed: no clear path found",
              severity="warning",
              payload={"behavior": "rotate_in_place", "attempt": 1,
                       "success": False},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 52.0, "recovery_started", "planner",
              "Recovery behavior started: backup",
              severity="warning", payload={"behavior": "backup", "attempt": 2},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 58.0, "recovery_completed", "planner",
              "Recovery backup completed: path still blocked",
              severity="warning",
              payload={"behavior": "backup", "attempt": 2, "success": False},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 60.0, "planner_state_changed", "planner",
              "Planner state: replanning — requesting alternate global route",
              payload={"state": "replanning"}, correlation_id=corr),
        event(base, 61.5, "warning_raised", "planner",
              "Global replan failed: no alternate route to goal",
              severity="warning",
              payload={"routes_evaluated": 3, "reason": "corridor_blocked"},
              correlation_id=corr, evidence_tags=["planner",
                                                  "no_alternate_route"]),
        event(base, 61.5, "planner_state_changed", "planner",
              "Planner state: avoiding", payload={"state": "avoiding"},
              correlation_id=corr),
        event(base, 64.0, "recovery_started", "planner",
              "Recovery behavior started: wait_and_retry",
              severity="warning",
              payload={"behavior": "wait_and_retry", "attempt": 3},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 76.0, "recovery_completed", "planner",
              "Recovery wait_and_retry completed: obstacle still present",
              severity="warning",
              payload={"behavior": "wait_and_retry", "attempt": 3,
                       "success": False},
              correlation_id=corr, evidence_tags=["recovery"]),
    ]

    for t in [round(v, 1) for v in frange(66.0, 89.0, 2.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            "cmd_vel linear=0.00 m/s angular=0.00 rad/s (holding position)",
            payload={"linear": 0.0, "angular": 0.0},
            correlation_id=corr, evidence_tags=["zero_velocity"]))

    events += [
        event(base, 88.0, "error_raised", "task_manager",
              "Task exceeded maximum duration of 90 s",
              severity="error", payload={"elapsed_s": 88.0, "limit_s": 90.0},
              correlation_id=corr, evidence_tags=["timeout"]),
        event(base, 90.0, "task_timed_out", "task_manager",
              "Task timed out after 3 failed recovery attempts",
              severity="error",
              payload={"timeout_s": 90, "recovery_attempts": 3},
              correlation_id=corr, evidence_tags=["timeout"]),
        event(base, 91.0, "task_failed", "task_manager",
              "Task 'Deliver pallet to Loading Bay B' failed: navigation "
              "timed out while blocked by an obstacle",
              severity="critical",
              payload={"reason": "navigation_timeout",
                       "final_goal_distance_m": 5.02},
              correlation_id=corr, evidence_tags=["timeout", "obstacle"]),
    ]

    return {
        "schema_version": "1.0",
        "id": "INC-2026-0728-001",
        "robot_id": "W-104",
        "robot_model": "Fetchbot AMR-600",
        "facility": "Warehouse 3 — Fremont",
        "task_name": "Deliver pallet to Loading Bay B",
        "task_goal": "Navigate from Pick Station 7 to Loading Bay B "
                     "(18.00, 6.50) and drop pallet PLT-88213",
        "start_time": iso(base, 0.0),
        "end_time": iso(base, duration),
        "outcome": "timed_out",
        "severity": "critical",
        "software_version": "nav-stack 2.14.1",
        "map_version": "warehouse3-2026.07.12",
        "environment": "Indoor warehouse, aisle corridor C, mixed traffic",
        "summary": "Robot W-104 stopped 0.4 m short of a pallet left in "
                   "aisle corridor C while en route to Loading Bay B. Three "
                   "recovery behaviors failed to find a path around the "
                   "obstacle and the task timed out after 90 s.",
        "events": events,
        "telemetry": [
            series("pos_x", "m", xs),
            series("pos_y", "m", ys),
            series("heading", "rad", hs),
            series("linear_velocity", "m/s", lin),
            series("angular_velocity", "rad/s", ang),
            series("obstacle_distance", "m", obs),
            series("goal_distance", "m", goal_dist),
            series("localization_confidence", "", loc),
            series("battery_pct", "%", battery),
            series("planner_state", "",
                   [(t, s) for t, s in planner_states]),
            series("recovery_count", "",
                   [(t, float(c)) for t, c in recovery_counts]),
        ],
    }


# ---------------------------------------------------------------------------
# Incident 2 — localization confidence collapse
# ---------------------------------------------------------------------------


def incident_localization() -> dict:
    base = datetime(2026, 7, 29, 14, 41, 20, tzinfo=timezone.utc)
    duration, dt = 60.0, 0.25
    times = sample_times(duration, dt)
    goal = (3.0, 14.0)
    corr = "TASK-4906"

    # Pose estimate jumps 3.4 m at t=27 when the particle filter diverges.
    x_keys = [
        (0, 16.0), (24, 9.6), (26.75, 8.9), (27, 5.6), (30, 5.4), (60, 5.4),
    ]
    y_keys = [
        (0, 12.0), (24, 12.6), (26.75, 12.7), (27, 13.5), (30, 13.6),
        (60, 13.6),
    ]
    h_keys = [(0, 3.05), (24, 3.05), (27, 2.4), (30, 2.4), (60, 2.4)]

    xs, ys, hs, lin, ang = motion_series(times, x_keys, y_keys, h_keys)

    def conf(t: float) -> float:
        keys = [
            (0, 0.97), (22, 0.96), (24, 0.95), (26, 0.62), (29, 0.35),
            (34, 0.22), (44, 0.28), (50, 0.31), (60, 0.30),
        ]
        return round(interp(keys, t), 4)

    loc = [(t, conf(t)) for t in times]
    obs = [(t, round(4.2 + 0.3 * math.sin(0.4 * t), 3)) for t in times]
    goal_dist = [(t, round(dist_to(x_keys, y_keys, t, *goal), 3)) for t in times]
    battery = [(t, round(41.0 - 0.010 * t, 3)) for t in times]

    planner_states = [
        (0.0, "executing"), (30.0, "waiting_for_localization"),
        (58.0, "failed"),
    ]
    recovery_counts = [(0.0, 0), (40.0, 1)]

    events = [
        event(base, 0.0, "task_started", "task_manager",
              "Task 'Return to charging dock' started",
              payload={"task": "return_to_dock", "dock_id": "DOCK-2"},
              correlation_id=corr),
        event(base, 0.4, "nav_goal_issued", "navigation",
              "Navigation goal issued: Dock 2 (3.00, 14.00)",
              payload={"goal_x": goal[0], "goal_y": goal[1], "frame": "map"},
              correlation_id=corr),
        event(base, 0.9, "planner_state_changed", "planner",
              "Planner state: executing", payload={"state": "executing"},
              correlation_id=corr),
    ]
    for t in [round(v, 1) for v in frange(2.0, 26.0, 3.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            f"cmd_vel linear={interp_val(lin, t):.2f} m/s",
            payload={"linear": interp_val(lin, t),
                     "angular": interp_val(ang, t)},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(4.0, 56.0, 4.0)]:
        events.append(event(
            base, t, "pose_updated", "localization",
            f"Pose ({interp(x_keys, t):.2f}, {interp(y_keys, t):.2f}) "
            f"conf={conf(t):.2f}",
            payload={"x": round(interp(x_keys, t), 3),
                     "y": round(interp(y_keys, t), 3),
                     "heading": round(interp(h_keys, t), 3),
                     "confidence": conf(t)},
            correlation_id=corr))

    events += [
        event(base, 25.0, "warning_raised", "localization",
              "AMCL particle spread increasing rapidly near reflective racking",
              severity="warning",
              payload={"particle_spread_m": 1.8, "n_particles": 2000},
              correlation_id=corr, evidence_tags=["localization"]),
        event(base, 27.0, "warning_raised", "localization",
              "Pose estimate jumped 3.41 m between updates",
              severity="warning", payload={"jump_m": 3.41},
              correlation_id=corr, evidence_tags=["localization",
                                                  "pose_jump"]),
        event(base, 30.0, "planner_state_changed", "planner",
              "Planner state: waiting_for_localization — pose untrusted",
              severity="warning",
              payload={"state": "waiting_for_localization"},
              correlation_id=corr, evidence_tags=["planner", "localization"]),
    ]
    for t in [round(v, 1) for v in frange(31.0, 43.0, 1.5)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            "cmd_vel linear=0.00 m/s angular=0.00 rad/s (pose untrusted)",
            payload={"linear": 0.0, "angular": 0.0},
            correlation_id=corr, evidence_tags=["zero_velocity"]))
    events += [
        event(base, 38.0, "error_raised", "localization",
              "Localization confidence 0.22 below minimum threshold 0.50",
              severity="error",
              payload={"confidence": 0.22, "threshold": 0.5},
              correlation_id=corr, evidence_tags=["localization"]),
        event(base, 40.0, "recovery_started", "localization",
              "Recovery behavior started: global_relocalize",
              severity="warning",
              payload={"behavior": "global_relocalize", "attempt": 1},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 50.0, "recovery_completed", "localization",
              "Recovery global_relocalize completed: confidence still 0.31",
              severity="warning",
              payload={"behavior": "global_relocalize", "attempt": 1,
                       "success": False},
              correlation_id=corr, evidence_tags=["recovery"]),
        event(base, 57.0, "error_raised", "task_manager",
              "Navigation cannot continue without a trusted pose estimate",
              severity="error", payload={"confidence": 0.30},
              correlation_id=corr, evidence_tags=["localization"]),
        event(base, 58.5, "task_failed", "task_manager",
              "Task 'Return to charging dock' failed: localization did not "
              "recover", severity="critical",
              payload={"reason": "localization_failure"},
              correlation_id=corr, evidence_tags=["localization"]),
    ]

    return {
        "schema_version": "1.0",
        "id": "INC-2026-0729-002",
        "robot_id": "W-087",
        "robot_model": "Fetchbot AMR-600",
        "facility": "Warehouse 3 — Fremont",
        "task_name": "Return to charging dock",
        "task_goal": "Navigate to charging dock DOCK-2 at (3.00, 14.00)",
        "start_time": iso(base, 0.0),
        "end_time": iso(base, duration),
        "outcome": "failed",
        "severity": "error",
        "software_version": "nav-stack 2.14.1",
        "map_version": "warehouse3-2026.07.12",
        "environment": "Indoor warehouse, aisle D near reflective racking",
        "summary": "Robot W-087's localization confidence collapsed from 97% "
                   "to 22% next to newly installed reflective racking. The "
                   "pose estimate jumped 3.4 m, the planner suspended "
                   "navigation, and relocalization failed to recover.",
        "events": events,
        "telemetry": [
            series("pos_x", "m", xs),
            series("pos_y", "m", ys),
            series("heading", "rad", hs),
            series("linear_velocity", "m/s", lin),
            series("angular_velocity", "rad/s", ang),
            series("obstacle_distance", "m", obs),
            series("goal_distance", "m", goal_dist),
            series("localization_confidence", "", loc),
            series("battery_pct", "%", battery),
            series("planner_state", "", planner_states),
            series("recovery_count", "",
                   [(t, float(c)) for t, c in recovery_counts]),
        ],
    }


# ---------------------------------------------------------------------------
# Incident 3 — controller oscillation in a narrow doorway
# ---------------------------------------------------------------------------


def incident_oscillation() -> dict:
    base = datetime(2026, 7, 30, 11, 5, 47, tzinfo=timezone.utc)
    duration, dt = 75.0, 0.25
    times = sample_times(duration, dt)
    goal = (14.0, 6.0)
    corr = "TASK-5012"

    x_keys = [(0, 2.0), (4, 3.2), (20, 7.0), (55, 7.35), (75, 7.35)]
    y_keys = [(0, 6.0), (75, 6.0)]

    def heading(t: float) -> float:
        if t < 20:
            return 0.0
        if t > 56:
            return 0.0
        # Doorway hunting: the controller wags the heading at ~0.33 Hz.
        return round(0.24 * math.sin(2.1 * (t - 20)), 4)

    xs, ys, _, lin, _ = motion_series(times, x_keys, y_keys, [(0, 0.0)])
    hs = [(t, heading(t)) for t in times]
    ang = []
    for i, t in enumerate(times):
        if i == 0:
            ang.append((t, 0.0))
        else:
            ang.append((t, round((heading(t) - heading(times[i - 1])) / dt, 4)))

    obs = [(t, round(0.86 + 0.06 * math.sin(1.3 * t), 3)) for t in times]
    goal_dist = [(t, round(dist_to(x_keys, y_keys, t, *goal), 3)) for t in times]
    loc = [(t, round(0.965 + 0.01 * math.sin(0.2 * t), 4)) for t in times]
    battery = [(t, round(77.0 - 0.011 * t, 3)) for t in times]

    planner_states = [
        (0.0, "executing"), (25.0, "replanning"), (26.5, "executing"),
        (33.0, "replanning"), (34.5, "executing"), (41.0, "replanning"),
        (42.5, "executing"), (49.0, "replanning"), (50.5, "executing"),
        (70.0, "failed"),
    ]

    events = [
        event(base, 0.0, "task_started", "task_manager",
              "Task 'Deliver parts bin to Assembly Cell 3' started",
              payload={"task": "deliver_bin", "destination": "Assembly Cell 3"},
              correlation_id=corr),
        event(base, 0.5, "nav_goal_issued", "navigation",
              "Navigation goal issued: Assembly Cell 3 (14.00, 6.00)",
              payload={"goal_x": goal[0], "goal_y": goal[1], "frame": "map"},
              correlation_id=corr),
        event(base, 1.0, "planner_state_changed", "planner",
              "Planner state: executing", payload={"state": "executing"},
              correlation_id=corr),
    ]
    for t in [round(v, 1) for v in frange(2.0, 19.0, 3.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            f"cmd_vel linear={interp_val(lin, t):.2f} m/s",
            payload={"linear": interp_val(lin, t), "angular": 0.0},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(5.0, 70.0, 5.0)]:
        events.append(event(
            base, t, "pose_updated", "localization",
            f"Pose ({interp(x_keys, t):.2f}, 6.00)",
            payload={"x": round(interp(x_keys, t), 3), "y": 6.0,
                     "heading": heading(t)},
            correlation_id=corr))

    # Alternating angular commands as the controller hunts in the doorway.
    sign = 1
    for t in [round(v, 2) for v in frange(21.0, 54.0, 1.5)]:
        w = round(sign * 0.72, 2)
        events.append(event(
            base, t, "velocity_command", "controller",
            f"cmd_vel linear=0.05 m/s angular={w:+.2f} rad/s",
            payload={"linear": 0.05, "angular": w},
            correlation_id=corr, evidence_tags=["oscillation"]))
        sign = -sign

    for i, t in enumerate([25.0, 33.0, 41.0, 49.0]):
        events.append(event(
            base, t, "planner_state_changed", "planner",
            f"Planner state: replanning (attempt {i + 1}) — local plan "
            "infeasible in doorway",
            severity="warning", payload={"state": "replanning"},
            correlation_id=corr, evidence_tags=["replanning"]))
        events.append(event(
            base, t + 1.5, "planner_state_changed", "planner",
            "Planner state: executing", payload={"state": "executing"},
            correlation_id=corr))

    events += [
        event(base, 35.0, "warning_raised", "controller",
              "Angular velocity command oscillation detected "
              "(11 sign changes in 15 s)",
              severity="warning",
              payload={"sign_changes": 11, "window_s": 15},
              correlation_id=corr, evidence_tags=["controller",
                                                  "oscillation"]),
        event(base, 56.0, "warning_raised", "navigation",
              "Progress watchdog: displacement 0.31 m in the last 35 s",
              severity="warning",
              payload={"displacement_m": 0.31, "window_s": 35},
              correlation_id=corr, evidence_tags=["progress"]),
        event(base, 70.0, "error_raised", "navigation",
              "Navigation aborted: controller failed to converge through "
              "doorway DW-2 (width 0.78 m)",
              severity="error",
              payload={"doorway_id": "DW-2", "doorway_width_m": 0.78,
                       "obstacle_x": 7.6, "obstacle_y": 6.0},
              correlation_id=corr, evidence_tags=["controller", "doorway"]),
        event(base, 72.0, "task_failed", "task_manager",
              "Task 'Deliver parts bin to Assembly Cell 3' aborted after "
              "controller oscillation in narrow doorway",
              severity="error",
              payload={"reason": "controller_oscillation"},
              correlation_id=corr, evidence_tags=["controller"]),
    ]

    return {
        "schema_version": "1.0",
        "id": "INC-2026-0730-003",
        "robot_id": "W-231",
        "robot_model": "Fetchbot AMR-450",
        "facility": "Warehouse 3 — Fremont",
        "task_name": "Deliver parts bin to Assembly Cell 3",
        "task_goal": "Navigate through doorway DW-2 to Assembly Cell 3 "
                     "(14.00, 6.00) with parts bin BIN-3341",
        "start_time": iso(base, 0.0),
        "end_time": iso(base, duration),
        "outcome": "aborted",
        "severity": "warning",
        "software_version": "nav-stack 2.14.1",
        "map_version": "warehouse3-2026.07.12",
        "environment": "Indoor warehouse, doorway DW-2 (0.78 m clear width)",
        "summary": "Robot W-231 stalled at doorway DW-2: the motion "
                   "controller alternated left/right turn commands at the "
                   "constriction, advanced only 0.35 m in 35 s despite four "
                   "replans, and the task was aborted.",
        "events": events,
        "telemetry": [
            series("pos_x", "m", xs),
            series("pos_y", "m", ys),
            series("heading", "rad", hs),
            series("linear_velocity", "m/s", lin),
            series("angular_velocity", "rad/s", ang),
            series("obstacle_distance", "m", obs),
            series("goal_distance", "m", goal_dist),
            series("localization_confidence", "", loc),
            series("battery_pct", "%", battery),
            series("planner_state", "", planner_states),
            series("recovery_count", "", [(0.0, 0.0)]),
        ],
    }


# ---------------------------------------------------------------------------
# Incident 4 — lidar / obstacle-sensor dropout
# ---------------------------------------------------------------------------


def incident_sensor_dropout() -> dict:
    base = datetime(2026, 7, 31, 16, 22, 9, tzinfo=timezone.utc)
    duration, dt = 70.0, 0.25
    times = sample_times(duration, dt)
    goal = (20.0, 3.0)
    corr = "TASK-5177"

    x_keys = [(0, 4.0), (30, 13.0), (34, 13.6), (58, 16.0), (62, 16.1),
              (70, 16.1)]
    y_keys = [(0, 3.0), (70, 3.0)]
    h_keys = [(0, 0.0), (70, 0.0)]

    xs, ys, hs, lin, ang = motion_series(times, x_keys, y_keys, h_keys)

    # Obstacle-distance samples stop at t=30 and resume at t=52 (22 s gap).
    obs_times = [t for t in sample_times(duration, 0.5) if t <= 30.0 or t >= 52.0]
    obs = [(t, round(3.6 + 0.25 * math.sin(0.5 * t), 3)) for t in obs_times]
    goal_dist = [(t, round(dist_to(x_keys, y_keys, t, *goal), 3)) for t in times]
    loc = [(t, round(0.955 + 0.012 * math.sin(0.18 * t), 4)) for t in times]
    battery = [(t, round(64.0 - 0.013 * t, 3)) for t in times]

    planner_states = [
        (0.0, "executing"), (34.0, "degraded"), (60.0, "failed"),
    ]

    events = [
        event(base, 0.0, "task_started", "task_manager",
              "Task 'Transfer tote to Outbound Staging' started",
              payload={"task": "transfer_tote", "tote_id": "TOTE-90412"},
              correlation_id=corr),
        event(base, 0.6, "nav_goal_issued", "navigation",
              "Navigation goal issued: Outbound Staging (20.00, 3.00)",
              payload={"goal_x": goal[0], "goal_y": goal[1], "frame": "map"},
              correlation_id=corr),
        event(base, 1.2, "planner_state_changed", "planner",
              "Planner state: executing", payload={"state": "executing"},
              correlation_id=corr),
    ]
    for t in [round(v, 1) for v in frange(2.0, 30.0, 3.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            f"cmd_vel linear={interp_val(lin, t):.2f} m/s",
            payload={"linear": interp_val(lin, t), "angular": 0.0},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(5.0, 65.0, 5.0)]:
        events.append(event(
            base, t, "pose_updated", "localization",
            f"Pose ({interp(x_keys, t):.2f}, 3.00)",
            payload={"x": round(interp(x_keys, t), 3), "y": 3.0,
                     "heading": 0.0},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(2.0, 30.0, 4.0)]:
        events.append(event(
            base, t, "obstacle_distance_updated", "perception",
            f"Nearest obstacle {3.6 + 0.25 * math.sin(0.5 * t):.2f} m",
            payload={"distance_m": round(3.6 + 0.25 * math.sin(0.5 * t), 3),
                     "source": "lidar_front"},
            correlation_id=corr))

    events += [
        event(base, 33.0, "warning_raised", "perception",
              "Lidar scan timestamps stale: last scan 3.1 s old",
              severity="warning",
              payload={"last_scan_age_s": 3.1, "topic": "/scan"},
              correlation_id=corr, evidence_tags=["sensor", "stale"]),
        event(base, 34.0, "planner_state_changed", "planner",
              "Planner state: degraded — reducing speed, no obstacle data",
              severity="warning", payload={"state": "degraded"},
              correlation_id=corr, evidence_tags=["planner", "degraded"]),
        event(base, 36.0, "velocity_command", "controller",
              "cmd_vel linear=0.20 m/s (degraded mode speed cap)",
              payload={"linear": 0.2, "angular": 0.0},
              correlation_id=corr),
        event(base, 45.0, "error_raised", "perception",
              "Obstacle sensor timeout: no scan received for 15 s",
              severity="error",
              payload={"gap_s": 15.0, "topic": "/scan",
                       "driver": "sick_tim781"},
              correlation_id=corr, evidence_tags=["sensor", "stale"]),
        event(base, 46.0, "velocity_command", "controller",
              "cmd_vel linear=0.12 m/s (degraded mode)",
              payload={"linear": 0.12, "angular": 0.0},
              correlation_id=corr),
        event(base, 52.0, "obstacle_distance_updated", "perception",
              "Lidar scans resumed after driver restart (gap 22.0 s)",
              severity="warning",
              payload={"distance_m": 3.42, "gap_s": 22.0,
                       "source": "lidar_front"},
              correlation_id=corr, evidence_tags=["sensor"]),
        event(base, 58.0, "warning_raised", "system",
              "Sensor health check failed twice in one task; flagging unit "
              "for maintenance", severity="warning",
              payload={"component": "lidar_front", "failures": 2},
              correlation_id=corr, evidence_tags=["sensor"]),
        event(base, 60.0, "error_raised", "navigation",
              "Cannot guarantee safe motion: obstacle data unreliable",
              severity="error", payload={"reason": "sensor_unreliable"},
              correlation_id=corr, evidence_tags=["sensor"]),
        event(base, 62.0, "velocity_command", "controller",
              "cmd_vel linear=0.00 m/s angular=0.00 rad/s (safe stop)",
              payload={"linear": 0.0, "angular": 0.0},
              correlation_id=corr),
        event(base, 64.0, "task_failed", "task_manager",
              "Task 'Transfer tote to Outbound Staging' failed: obstacle "
              "sensor dropout", severity="error",
              payload={"reason": "sensor_dropout"},
              correlation_id=corr, evidence_tags=["sensor"]),
    ]

    return {
        "schema_version": "1.0",
        "id": "INC-2026-0731-004",
        "robot_id": "W-058",
        "robot_model": "Fetchbot AMR-600",
        "facility": "Warehouse 3 — Fremont",
        "task_name": "Transfer tote to Outbound Staging",
        "task_goal": "Carry tote TOTE-90412 to Outbound Staging (20.00, 3.00)",
        "start_time": iso(base, 0.0),
        "end_time": iso(base, duration),
        "outcome": "failed",
        "severity": "error",
        "software_version": "nav-stack 2.14.1",
        "map_version": "warehouse3-2026.07.12",
        "environment": "Indoor warehouse, main transit lane",
        "summary": "Robot W-058's front lidar stopped publishing for 22 s "
                   "mid-transit. The planner dropped to degraded mode, "
                   "capped speed, and safely stopped the task when obstacle "
                   "data could not be trusted.",
        "events": events,
        "telemetry": [
            series("pos_x", "m", xs),
            series("pos_y", "m", ys),
            series("heading", "rad", hs),
            series("linear_velocity", "m/s", lin),
            series("angular_velocity", "rad/s", ang),
            series("obstacle_distance", "m", obs),
            series("goal_distance", "m", goal_dist),
            series("localization_confidence", "", loc),
            series("battery_pct", "%", battery),
            series("planner_state", "", planner_states),
            series("recovery_count", "", [(0.0, 0.0)]),
        ],
    }


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Baseline — the same delivery task completing normally (for incident diffing)
# ---------------------------------------------------------------------------


def incident_baseline() -> dict:
    """A successful run of the primary task, one week before the failure.

    Mirrors INC-2026-0728-001's route for the first ~26 s so a diff shows
    near-zero deltas until the pallet blockage, then continues to the goal.
    """
    base = datetime(2026, 7, 21, 9, 2, 11, tzinfo=timezone.utc)
    duration, dt = 58.0, 0.2
    times = sample_times(duration, dt)
    goal = (18.0, 6.5)
    corr = "TASK-4655"

    x_keys = [
        (0, 2.0), (2, 2.8), (12, 10.0), (16, 11.6), (26, 13.0), (32, 14.2),
        (40, 16.0), (48, 17.6), (52, 18.0), (58, 18.0),
    ]
    y_keys = [
        (0, 2.0), (12, 2.0), (16, 3.0), (26, 4.8), (32, 5.4), (40, 6.0),
        (48, 6.4), (52, 6.5), (58, 6.5),
    ]
    h_keys = [
        (0, 0.0), (12, 0.0), (16, 0.55), (24, 0.85), (40, 0.5), (48, 0.3),
        (52, 0.2), (58, 0.2),
    ]

    xs, ys, hs, lin, ang = motion_series(times, x_keys, y_keys, h_keys)

    def clearance(t: float) -> float:
        # Corridor is clear the whole way; lidar reports near max range.
        return round(4.6 + 0.3 * math.sin(0.4 * t), 3)

    obs = [(t, clearance(t)) for t in times]
    goal_dist = [
        (t, round(dist_to(x_keys, y_keys, t, *goal), 3)) for t in times
    ]
    loc = [(t, round(0.97 + 0.015 * math.sin(0.15 * t), 4)) for t in times]
    battery = [(t, round(95.5 - 0.012 * t, 3)) for t in times]

    planner_states = [
        (0.0, "idle"), (0.8, "planning"), (1.5, "executing"),
        (56.0, "succeeded"),
    ]

    events: list[dict] = [
        event(base, 0.0, "task_started", "task_manager",
              "Task 'Deliver pallet to Loading Bay B' started",
              payload={"task": "deliver_pallet", "destination": "Loading Bay B"},
              correlation_id=corr),
        event(base, 0.5, "nav_goal_issued", "navigation",
              "Navigation goal issued: Loading Bay B (18.00, 6.50)",
              payload={"goal_x": goal[0], "goal_y": goal[1],
                       "frame": "map", "tolerance_m": 0.25},
              correlation_id=corr),
        event(base, 0.8, "planner_state_changed", "planner",
              "Planner state: planning", payload={"state": "planning"},
              correlation_id=corr),
        event(base, 1.5, "planner_state_changed", "planner",
              "Planner state: executing (global path 17.6 m)",
              payload={"state": "executing", "path_length_m": 17.6},
              correlation_id=corr),
    ]

    for t in [round(v, 1) for v in frange(2.0, 54.0, 4.0)]:
        events.append(event(
            base, t, "velocity_command", "controller",
            f"cmd_vel linear={interp_val(lin, t):.2f} m/s "
            f"angular={interp_val(ang, t):.2f} rad/s",
            payload={"linear": interp_val(lin, t), "angular": interp_val(ang, t)},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(5.0, 55.0, 5.0)]:
        events.append(event(
            base, t, "pose_updated", "localization",
            f"Pose ({interp(x_keys, t):.2f}, {interp(y_keys, t):.2f}) "
            f"θ={interp(h_keys, t):.2f}",
            payload={"x": round(interp(x_keys, t), 3),
                     "y": round(interp(y_keys, t), 3),
                     "heading": round(interp(h_keys, t), 3),
                     "covariance_trace": 0.013},
            correlation_id=corr))
    for t in [round(v, 1) for v in frange(20.0, 52.0, 8.0)]:
        events.append(event(
            base, t, "obstacle_distance_updated", "perception",
            f"Nearest obstacle {clearance(t):.2f} m",
            payload={"distance_m": clearance(t),
                     "bearing_rad": 0.82, "source": "lidar_front"},
            correlation_id=corr))

    events.append(event(
        base, 56.0, "planner_state_changed", "planner",
        "Planner state: succeeded — goal reached (18.00, 6.50)",
        payload={"state": "succeeded", "final_goal_distance_m": 0.08},
        correlation_id=corr))

    return {
        "schema_version": "1.0",
        "id": "INC-2026-0721-BASE",
        "robot_id": "W-104",
        "robot_model": "Fetchbot AMR-600",
        "facility": "Warehouse 3 — Fremont",
        "task_name": "Deliver pallet to Loading Bay B",
        "task_goal": "Navigate from Pick Station 7 to Loading Bay B "
                     "(18.00, 6.50) and drop pallet PLT-87710",
        "start_time": iso(base, 0.0),
        "end_time": iso(base, duration),
        "outcome": "success",
        "severity": "info",
        "software_version": "nav-stack 2.14.1",
        "map_version": "warehouse3-2026.07.12",
        "environment": "Indoor warehouse, aisle corridor C, mixed traffic",
        "summary": "Baseline run: W-104 completed the same delivery to "
                   "Loading Bay B in 58 s through a clear aisle corridor C. "
                   "Recorded as a known-good reference for incident diffing.",
        "events": events,
        "telemetry": [
            series("pos_x", "m", xs),
            series("pos_y", "m", ys),
            series("heading", "rad", hs),
            series("linear_velocity", "m/s", lin),
            series("angular_velocity", "rad/s", ang),
            series("obstacle_distance", "m", obs),
            series("goal_distance", "m", goal_dist),
            series("localization_confidence", "", loc),
            series("battery_pct", "%", battery),
            series("planner_state", "",
                   [(t, s) for t, s in planner_states]),
        ],
    }


def frange(start: float, stop: float, step: float) -> list[float]:
    out = []
    v = start
    while v <= stop + 1e-9:
        out.append(round(v, 6))
        v += step
    return out


def interp_val(samples: list[tuple[float, float]], t: float) -> float:
    return round(interp(samples, t), 3)


GENERATORS = [
    incident_obstacle,
    incident_localization,
    incident_oscillation,
    incident_sensor_dropout,
    incident_baseline,
]


def generate_all() -> list[dict]:
    return [g() for g in GENERATORS]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for incident in generate_all():
        path = OUT_DIR / f"{incident['id']}.json"
        path.write_text(json.dumps(incident, indent=2) + "\n")
        n_samples = sum(len(s["samples"]) for s in incident["telemetry"])
        print(f"wrote {path} ({len(incident['events'])} events, "
              f"{n_samples} telemetry samples)")


if __name__ == "__main__":
    main()
