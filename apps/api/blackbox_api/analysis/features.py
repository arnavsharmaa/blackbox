"""Derived, deterministic features computed from raw incident data.

Every rule in rules.py consumes IncidentFeatures instead of poking at raw
events/telemetry, so the numeric definitions (streaks, gaps, windows) live in
exactly one place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from blackbox_api.analysis.thresholds import AnalysisThresholds, get_thresholds
from blackbox_api.schemas import (
    EventType,
    Incident,
    IncidentEvent,
    TelemetryChannel,
)

Point = tuple[float, float]  # (t, value)


@dataclass(frozen=True)
class Interval:
    t_start: float
    t_end: float
    min_value: float

    @property
    def duration(self) -> float:
        return self.t_end - self.t_start


@dataclass(frozen=True)
class RecoveryAttempt:
    behavior: str
    t_start: float
    t_end: float | None
    succeeded: bool


@dataclass
class IncidentFeatures:
    duration_s: float
    # velocity commands (from events)
    zero_cmd_streak: int = 0
    zero_cmd_streak_t: float = 0.0
    zero_cmd_total: int = 0
    # obstacle
    obstacle_low_interval: Interval | None = None
    obstacle_min: float | None = None
    # motion
    total_displacement: float = 0.0
    displacement_during_recoveries: float | None = None
    # recoveries
    recoveries: list[RecoveryAttempt] = field(default_factory=list)
    # localization
    loc_conf_min: float | None = None
    loc_conf_mean: float | None = None
    loc_conf_max_drop: float = 0.0
    loc_conf_drop_t: float | None = None
    max_pose_jump: float = 0.0
    max_pose_jump_t: float | None = None
    # controller
    angular_flips: int = 0
    angular_flip_window: tuple[float, float] | None = None
    progress_in_flip_window: float | None = None
    mean_abs_linear_in_flip_window: float | None = None
    replan_count: int = 0
    # sensor freshness
    obstacle_median_gap: float | None = None
    obstacle_max_gap: float = 0.0
    obstacle_max_gap_t: float | None = None
    sensor_stale_warning_ts: list[float] = field(default_factory=list)
    # states / outcome flags
    planner_states: list[str] = field(default_factory=list)
    timed_out: bool = False
    task_failed: bool = False
    goal_issued: bool = False
    goal_active_at_end: bool = False
    timeout_t: float | None = None
    failure_t: float | None = None


def event_t(incident: Incident, event: IncidentEvent) -> float:
    return (event.timestamp - incident.start_time).total_seconds()


def numeric_series(incident: Incident, channel: TelemetryChannel) -> list[Point]:
    for series in incident.telemetry:
        if series.channel == channel:
            return [
                (s.t, float(s.value))
                for s in series.samples
                if isinstance(s.value, (int, float))
            ]
    return []


def string_series(
    incident: Incident, channel: TelemetryChannel
) -> list[tuple[float, str]]:
    for series in incident.telemetry:
        if series.channel == channel:
            return [(s.t, s.value) for s in series.samples if isinstance(s.value, str)]
    return []


def _longest_interval_below(points: list[Point], threshold: float) -> Interval | None:
    best: Interval | None = None
    start: float | None = None
    low_min = math.inf
    prev_t = 0.0
    for t, v in points:
        if v < threshold:
            if start is None:
                start = t
                low_min = v
            low_min = min(low_min, v)
            prev_t = t
        else:
            if start is not None:
                candidate = Interval(start, prev_t, low_min)
                if best is None or candidate.duration > best.duration:
                    best = candidate
                start, low_min = None, math.inf
    if start is not None:
        candidate = Interval(start, prev_t, low_min)
        if best is None or candidate.duration > best.duration:
            best = candidate
    return best


def _displacement(xs: list[Point], ys: list[Point], t0: float, t1: float) -> float:
    """Straight-line displacement of the robot between t0 and t1."""

    def at(points: list[Point], t: float) -> float | None:
        prev: Point | None = None
        for pt, pv in points:
            if pt >= t:
                return pv if prev is None else prev[1]
            prev = (pt, pv)
        return prev[1] if prev else None

    x0, x1 = at(xs, t0), at(xs, t1)
    y0, y1 = at(ys, t0), at(ys, t1)
    if x0 is None or x1 is None or y0 is None or y1 is None:
        return 0.0
    return math.hypot(x1 - x0, y1 - y0)


def compute_features(
    incident: Incident, thresholds: AnalysisThresholds | None = None
) -> IncidentFeatures:
    th = thresholds or get_thresholds()
    f = IncidentFeatures(duration_s=incident.duration_s)

    xs = numeric_series(incident, TelemetryChannel.POS_X)
    ys = numeric_series(incident, TelemetryChannel.POS_Y)
    obstacle = numeric_series(incident, TelemetryChannel.OBSTACLE_DISTANCE)
    loc = numeric_series(incident, TelemetryChannel.LOCALIZATION_CONFIDENCE)

    # --- velocity command streaks (from events, the controller's own record)
    streak = 0
    streak_start_t = 0.0
    for ev in incident.events:
        if ev.event_type != EventType.VELOCITY_COMMAND:
            continue
        linear = float(ev.payload.get("linear", 0.0))
        angular = float(ev.payload.get("angular", 0.0))
        if abs(linear) < th.zero_cmd_eps and abs(angular) < th.zero_cmd_eps:
            if streak == 0:
                streak_start_t = event_t(incident, ev)
            streak += 1
            f.zero_cmd_total += 1
            if streak > f.zero_cmd_streak:
                f.zero_cmd_streak = streak
                f.zero_cmd_streak_t = streak_start_t
        else:
            streak = 0

    # --- obstacle proximity
    if obstacle:
        f.obstacle_min = min(v for _, v in obstacle)
        f.obstacle_low_interval = _longest_interval_below(
            obstacle, th.obstacle_safety_threshold_m
        )
        gaps = [
            (b[0] - a[0], a[0])
            for a, b in zip(obstacle, obstacle[1:], strict=False)
        ]
        if gaps:
            sorted_gaps = sorted(g for g, _ in gaps)
            f.obstacle_median_gap = sorted_gaps[len(sorted_gaps) // 2]
            f.obstacle_max_gap, f.obstacle_max_gap_t = max(gaps)

    # --- motion
    if xs and ys:
        f.total_displacement = _displacement(xs, ys, 0.0, incident.duration_s)

    # --- recovery attempts
    open_recoveries: dict[str, float] = {}
    for ev in incident.events:
        t = event_t(incident, ev)
        behavior = str(ev.payload.get("behavior", "unknown"))
        if ev.event_type == EventType.RECOVERY_STARTED:
            open_recoveries[behavior] = t
        elif ev.event_type == EventType.RECOVERY_COMPLETED:
            start = open_recoveries.pop(behavior, t)
            f.recoveries.append(
                RecoveryAttempt(
                    behavior=behavior,
                    t_start=start,
                    t_end=t,
                    succeeded=bool(ev.payload.get("success", False)),
                )
            )
    for behavior, start in open_recoveries.items():
        f.recoveries.append(
            RecoveryAttempt(
                behavior=behavior, t_start=start, t_end=None, succeeded=False
            )
        )
    f.recoveries.sort(key=lambda r: r.t_start)
    if f.recoveries and xs and ys:
        first = f.recoveries[0].t_start
        last = max(
            r.t_end if r.t_end is not None else f.duration_s
            for r in f.recoveries
        )
        f.displacement_during_recoveries = _displacement(xs, ys, first, last)

    # --- localization
    if loc:
        values = [v for _, v in loc]
        f.loc_conf_min = min(values)
        f.loc_conf_mean = sum(values) / len(values)
        window = 5.0
        for i, (t_i, v_i) in enumerate(loc):
            for t_j, v_j in loc[i + 1 :]:
                if t_j - t_i > window:
                    break
                drop = v_i - v_j
                if drop > f.loc_conf_max_drop:
                    f.loc_conf_max_drop = drop
                    f.loc_conf_drop_t = t_j
    if xs and ys:
        for (ta, xa), (tb, xb) in zip(xs, xs[1:], strict=False):
            ya = next((v for t, v in ys if t == ta), None)
            yb = next((v for t, v in ys if t == tb), None)
            if ya is None or yb is None:
                continue
            jump = math.hypot(xb - xa, yb - ya)
            if jump > f.max_pose_jump:
                f.max_pose_jump = jump
                f.max_pose_jump_t = tb

    # --- controller oscillation (sign alternation of commanded angular velocity)
    ang_cmds: list[tuple[float, float]] = []
    for ev in incident.events:
        if ev.event_type == EventType.VELOCITY_COMMAND:
            ang_cmds.append(
                (event_t(incident, ev), float(ev.payload.get("angular", 0.0)))
            )
    flips = 0
    flip_ts: list[float] = []
    prev_sign = 0
    for t, w in ang_cmds:
        if abs(w) < th.angular_flip_min_rad_s:
            continue
        sign = 1 if w > 0 else -1
        if prev_sign != 0 and sign != prev_sign:
            flips += 1
            flip_ts.append(t)
        prev_sign = sign
    f.angular_flips = flips
    if flip_ts:
        f.angular_flip_window = (flip_ts[0], flip_ts[-1])
        if xs and ys:
            f.progress_in_flip_window = _displacement(xs, ys, flip_ts[0], flip_ts[-1])
        lin = numeric_series(incident, TelemetryChannel.LINEAR_VELOCITY)
        in_window = [abs(v) for t, v in lin if flip_ts[0] <= t <= flip_ts[-1]]
        if in_window:
            f.mean_abs_linear_in_flip_window = sum(in_window) / len(in_window)

    # --- sensor staleness warnings raised by diagnostics
    for ev in incident.events:
        if ev.event_type in (EventType.WARNING_RAISED, EventType.ERROR_RAISED) and (
            "sensor" in ev.evidence_tags or "stale" in ev.evidence_tags
        ):
            f.sensor_stale_warning_ts.append(event_t(incident, ev))

    # --- planner states / outcome flags
    goal_reached = False
    for ev in incident.events:
        t = event_t(incident, ev)
        if ev.event_type == EventType.PLANNER_STATE_CHANGED:
            state = str(ev.payload.get("state", ""))
            if state:
                f.planner_states.append(state)
                if state == "replanning":
                    f.replan_count += 1
                if state == "succeeded":
                    goal_reached = True
        elif ev.event_type == EventType.NAV_GOAL_ISSUED:
            f.goal_issued = True
        elif ev.event_type == EventType.TASK_TIMED_OUT:
            f.timed_out = True
            f.timeout_t = t
        elif ev.event_type == EventType.TASK_FAILED:
            f.task_failed = True
            f.failure_t = t
    f.goal_active_at_end = f.goal_issued and not goal_reached
    return f
