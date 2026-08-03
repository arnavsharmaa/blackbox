"""Deterministic diagnosis rules.

Each rule scores an incident against a set of weighted conditions and emits
evidence anchored to timestamps. No rule consults an LLM; confidence is the
normalized sum of satisfied condition weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from blackbox_api.analysis.features import (
    ANGULAR_FLIP_MIN_RAD_S,
    OBSTACLE_SAFETY_THRESHOLD_M,
    IncidentFeatures,
)
from blackbox_api.schemas import EvidenceItem, FailureCategory, TelemetryChannel


@dataclass
class RuleResult:
    rule_id: str
    category: FailureCategory
    score: float
    evidence: list[EvidenceItem] = field(default_factory=list)
    explanation: str = ""
    recommended_actions: list[str] = field(default_factory=list)
    conditions_met: list[str] = field(default_factory=list)


class _Scorer:
    """Accumulates weighted conditions and auto-numbered evidence."""

    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        self.total_weight = 0.0
        self.earned = 0.0
        self.conditions: list[str] = []
        self.evidence: list[EvidenceItem] = []

    def condition(
        self,
        met: bool,
        weight: float,
        label: str,
        *,
        summary: str | None = None,
        detail: str = "",
        t: float = 0.0,
        t_end: float | None = None,
        channel: TelemetryChannel | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        self.total_weight += weight
        if met:
            self.earned += weight
            self.conditions.append(label)
            if summary:
                self.evidence.append(
                    EvidenceItem(
                        id=f"{self.rule_id}-e{len(self.evidence) + 1}",
                        summary=summary,
                        detail=detail,
                        t=max(t, 0.0),
                        t_end=t_end,
                        channel=channel,
                        tags=tags or [],
                    )
                )
        return met

    def support(
        self,
        summary: str,
        *,
        detail: str = "",
        t: float = 0.0,
        t_end: float | None = None,
        channel: TelemetryChannel | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Evidence that supports the diagnosis without scoring it."""
        self.evidence.append(
            EvidenceItem(
                id=f"{self.rule_id}-e{len(self.evidence) + 1}",
                summary=summary,
                detail=detail,
                t=max(t, 0.0),
                t_end=t_end,
                channel=channel,
                tags=tags or [],
            )
        )

    @property
    def score(self) -> float:
        return round(self.earned / self.total_weight, 3) if self.total_weight else 0.0


def rule_persistent_obstacle(f: IncidentFeatures) -> RuleResult:
    s = _Scorer("persistent-obstacle")
    low = f.obstacle_low_interval
    s.condition(
        low is not None and low.duration >= 5.0,
        0.25,
        "obstacle_below_threshold",
        summary=(
            f"Obstacle distance remained below {OBSTACLE_SAFETY_THRESHOLD_M:.2f} m "
            f"for {low.duration:.1f} s (minimum {low.min_value:.2f} m)"
            if low
            else None
        ),
        detail="Sustained sub-threshold clearance means the local planner could "
        "not admit any forward trajectory.",
        t=low.t_start if low else 0.0,
        t_end=low.t_end if low else None,
        channel=TelemetryChannel.OBSTACLE_DISTANCE,
        tags=["obstacle", "safety_threshold"],
    )
    s.condition(
        f.zero_cmd_streak >= 5,
        0.20,
        "repeated_zero_velocity",
        summary=(
            f"{f.zero_cmd_streak} consecutive zero-velocity commands were issued "
            f"starting at t={f.zero_cmd_streak_t:.1f} s"
        ),
        detail="The controller repeatedly commanded a full stop instead of "
        "unsafe motion — correct behavior when no collision-free path exists.",
        t=f.zero_cmd_streak_t,
        tags=["controller", "zero_velocity"],
    )
    s.condition(
        len(f.recoveries) >= 2,
        0.15,
        "multiple_recovery_attempts",
        summary=(
            f"{len(f.recoveries)} recovery behaviors were attempted "
            f"({', '.join(r.behavior for r in f.recoveries)}), none succeeded"
            if f.recoveries and not any(r.succeeded for r in f.recoveries)
            else f"{len(f.recoveries)} recovery behaviors were attempted"
        ),
        t=f.recoveries[0].t_start if f.recoveries else 0.0,
        t_end=f.recoveries[-1].t_end if f.recoveries else None,
        tags=["recovery"],
    )
    s.condition(
        f.displacement_during_recoveries is not None
        and f.displacement_during_recoveries < 0.3,
        0.15,
        "no_position_change",
        summary=(
            f"Robot displacement was only "
            f"{f.displacement_during_recoveries:.2f} m across all recovery attempts"
            if f.displacement_during_recoveries is not None
            else None
        ),
        t=f.recoveries[0].t_start if f.recoveries else 0.0,
        channel=TelemetryChannel.POS_X,
        tags=["motion", "recovery"],
    )
    s.condition(
        f.goal_active_at_end,
        0.10,
        "goal_still_active",
        summary="The navigation goal remained active until the task ended",
        t=f.timeout_t or f.failure_t or f.duration_s,
        tags=["goal"],
    )
    s.condition(
        f.timed_out,
        0.15,
        "task_timed_out",
        summary=(
            f"Task timed out at t={f.timeout_t:.1f} s after recovery attempt "
            f"{len(f.recoveries)}"
            if f.timeout_t is not None
            else None
        ),
        t=f.timeout_t or f.duration_s,
        tags=["timeout"],
    )
    if f.loc_conf_min is not None and f.loc_conf_min >= 0.9:
        s.support(
            f"Localization confidence remained above "
            f"{f.loc_conf_min * 100:.0f}% for the entire incident",
            detail="Rules out localization failure as the cause of the stop.",
            t=0.0,
            t_end=f.duration_s,
            channel=TelemetryChannel.LOCALIZATION_CONFIDENCE,
            tags=["localization", "exculpatory"],
        )
    return RuleResult(
        rule_id="persistent_obstacle_blockage",
        category=FailureCategory.PERSISTENT_OBSTACLE,
        score=s.score,
        evidence=s.evidence,
        conditions_met=s.conditions,
        explanation=(
            "The local planner could not produce a collision-free path around a "
            "persistent obstacle. Clearance stayed below the safety threshold, the "
            "controller correctly held zero velocity, and repeated recovery "
            "behaviors produced no meaningful displacement before the task "
            "timed out."
        ),
        recommended_actions=[
            "Review the obstacle location on the facility map and confirm whether "
            "it is a mapped fixture or transient blockage",
            "Check perception logs to classify the obstacle (pallet, person, "
            "spill) at the blockage timestamp",
            "Evaluate whether the global planner should have been triggered to "
            "find an alternate aisle route",
            "Consider raising a facility alert when recovery behaviors fail "
            "twice consecutively",
        ],
    )


def rule_localization_failure(f: IncidentFeatures) -> RuleResult:
    s = _Scorer("localization-failure")
    s.condition(
        f.loc_conf_min is not None and f.loc_conf_min < 0.5,
        0.30,
        "confidence_collapse",
        summary=(
            f"Localization confidence collapsed to a minimum of "
            f"{f.loc_conf_min * 100:.0f}%"
            if f.loc_conf_min is not None
            else None
        ),
        t=f.loc_conf_drop_t or 0.0,
        channel=TelemetryChannel.LOCALIZATION_CONFIDENCE,
        tags=["localization"],
    )
    s.condition(
        f.loc_conf_max_drop > 0.4,
        0.20,
        "rapid_confidence_drop",
        summary=(
            f"Confidence dropped {f.loc_conf_max_drop * 100:.0f} percentage points "
            f"within 5 s around t={f.loc_conf_drop_t:.1f} s"
            if f.loc_conf_drop_t is not None
            else None
        ),
        t=f.loc_conf_drop_t or 0.0,
        channel=TelemetryChannel.LOCALIZATION_CONFIDENCE,
        tags=["localization"],
    )
    s.condition(
        f.max_pose_jump > 1.0,
        0.20,
        "pose_jump",
        summary=(
            f"Estimated pose jumped {f.max_pose_jump:.2f} m between consecutive "
            f"updates at t={f.max_pose_jump_t:.1f} s"
            if f.max_pose_jump_t is not None
            else None
        ),
        t=f.max_pose_jump_t or 0.0,
        channel=TelemetryChannel.POS_X,
        tags=["localization", "pose_jump"],
    )
    s.condition(
        "waiting_for_localization" in f.planner_states,
        0.15,
        "planner_waiting_for_localization",
        summary="Planner entered waiting_for_localization and suspended navigation",
        t=f.loc_conf_drop_t or 0.0,
        channel=TelemetryChannel.PLANNER_STATE,
        tags=["planner", "localization"],
    )
    s.condition(
        f.task_failed or f.timed_out,
        0.15,
        "navigation_failure",
        summary=(
            f"Task ended in failure at "
            f"t={(f.failure_t or f.timeout_t or f.duration_s):.1f} s"
        ),
        t=f.failure_t or f.timeout_t or f.duration_s,
        tags=["outcome"],
    )
    return RuleResult(
        rule_id="localization_failure",
        category=FailureCategory.LOCALIZATION_FAILURE,
        score=s.score,
        evidence=s.evidence,
        conditions_met=s.conditions,
        explanation=(
            "The localization estimate became unreliable: confidence collapsed "
            "and the pose estimate jumped discontinuously. The planner correctly "
            "suspended navigation rather than acting on an untrusted pose, and "
            "the task failed."
        ),
        recommended_actions=[
            "Inspect the AMCL/particle-filter logs around the confidence drop",
            "Check for reflective surfaces, moved racking, or map drift in the "
            "area where confidence collapsed",
            "Verify the map version deployed to the robot matches the facility "
            "layout",
            "Consider triggering an automatic relocalization routine when "
            "confidence drops below 50%",
        ],
    )


def rule_controller_oscillation(f: IncidentFeatures) -> RuleResult:
    s = _Scorer("controller-oscillation")
    window = f.angular_flip_window
    s.condition(
        f.angular_flips >= 8,
        0.30,
        "rapid_angular_alternation",
        summary=(
            f"Commanded angular velocity flipped sign {f.angular_flips} times "
            f"(|ω| ≥ {ANGULAR_FLIP_MIN_RAD_S} rad/s) between "
            f"t={window[0]:.1f} s and t={window[1]:.1f} s"
            if window
            else None
        ),
        t=window[0] if window else 0.0,
        t_end=window[1] if window else None,
        channel=TelemetryChannel.ANGULAR_VELOCITY,
        tags=["controller", "oscillation"],
    )
    s.condition(
        f.progress_in_flip_window is not None and f.progress_in_flip_window < 0.5,
        0.25,
        "little_forward_progress",
        summary=(
            f"Robot advanced only {f.progress_in_flip_window:.2f} m during the "
            f"oscillation window"
            if f.progress_in_flip_window is not None
            else None
        ),
        t=window[0] if window else 0.0,
        channel=TelemetryChannel.GOAL_DISTANCE,
        tags=["motion"],
    )
    s.condition(
        f.replan_count >= 2,
        0.20,
        "repeated_replanning",
        summary=f"Planner re-planned {f.replan_count} times without progress",
        t=window[0] if window else 0.0,
        channel=TelemetryChannel.PLANNER_STATE,
        tags=["planner", "replanning"],
    )
    s.condition(
        f.mean_abs_linear_in_flip_window is not None
        and f.mean_abs_linear_in_flip_window < 0.15,
        0.15,
        "low_linear_velocity",
        summary=(
            f"Mean linear speed during oscillation was only "
            f"{f.mean_abs_linear_in_flip_window:.2f} m/s"
            if f.mean_abs_linear_in_flip_window is not None
            else None
        ),
        t=window[0] if window else 0.0,
        channel=TelemetryChannel.LINEAR_VELOCITY,
        tags=["controller"],
    )
    s.condition(
        f.task_failed or f.timed_out,
        0.10,
        "task_not_completed",
        summary=(
            f"Task ended unsuccessfully at "
            f"t={(f.failure_t or f.timeout_t or f.duration_s):.1f} s"
        ),
        t=f.failure_t or f.timeout_t or f.duration_s,
        tags=["outcome"],
    )
    return RuleResult(
        rule_id="controller_oscillation",
        category=FailureCategory.CONTROLLER_OSCILLATION,
        score=s.score,
        evidence=s.evidence,
        conditions_met=s.conditions,
        explanation=(
            "The motion controller oscillated: angular velocity commands "
            "alternated sign rapidly while forward progress stalled, and the "
            "planner kept re-planning through the same constricted space. This "
            "pattern is typical of a controller gain/clearance mismatch in "
            "narrow passages."
        ),
        recommended_actions=[
            "Review DWB/TEB critic weights and angular acceleration limits for "
            "narrow-passage tuning",
            "Check the costmap inflation radius against the doorway width",
            "Reproduce in simulation with the recorded map and goal to tune "
            "controller parameters",
            "Consider adding a doorway-specific speed profile",
        ],
    )


def rule_sensor_dropout(f: IncidentFeatures) -> RuleResult:
    s = _Scorer("sensor-dropout")
    median = f.obstacle_median_gap
    dropout = (
        median is not None
        and median > 0
        and f.obstacle_max_gap > max(5 * median, 2.0)
    )
    s.condition(
        dropout,
        0.35,
        "missing_sensor_updates",
        summary=(
            f"Obstacle-sensor updates stopped for {f.obstacle_max_gap:.1f} s "
            f"starting at t={f.obstacle_max_gap_t:.1f} s "
            f"(normal update interval {median:.1f} s)"
            if dropout and f.obstacle_max_gap_t is not None and median is not None
            else None
        ),
        t=f.obstacle_max_gap_t or 0.0,
        t_end=(
            (f.obstacle_max_gap_t or 0.0) + f.obstacle_max_gap if dropout else None
        ),
        channel=TelemetryChannel.OBSTACLE_DISTANCE,
        tags=["sensor", "dropout"],
    )
    degraded_after = False
    if dropout and f.obstacle_max_gap_t is not None:
        degraded_after = "degraded" in f.planner_states or "conservative" in "".join(
            f.planner_states
        )
    s.condition(
        degraded_after,
        0.25,
        "planner_degraded_after_dropout",
        summary="Planner dropped to a degraded/conservative mode after sensor "
        "updates stopped",
        t=(f.obstacle_max_gap_t or 0.0) + (f.obstacle_max_gap or 0.0),
        channel=TelemetryChannel.PLANNER_STATE,
        tags=["planner", "degraded"],
    )
    s.condition(
        len(f.sensor_stale_warning_ts) >= 1,
        0.25,
        "stale_timestamp_warnings",
        summary=(
            f"Diagnostics raised {len(f.sensor_stale_warning_ts)} stale-sensor "
            f"warning(s), first at t={f.sensor_stale_warning_ts[0]:.1f} s"
            if f.sensor_stale_warning_ts
            else None
        ),
        t=f.sensor_stale_warning_ts[0] if f.sensor_stale_warning_ts else 0.0,
        tags=["sensor", "diagnostics"],
    )
    s.condition(
        f.task_failed or f.timed_out,
        0.15,
        "task_not_completed",
        summary=(
            f"Task ended unsuccessfully at "
            f"t={(f.failure_t or f.timeout_t or f.duration_s):.1f} s"
        ),
        t=f.failure_t or f.timeout_t or f.duration_s,
        tags=["outcome"],
    )
    return RuleResult(
        rule_id="sensor_dropout",
        category=FailureCategory.SENSOR_DROPOUT,
        score=s.score,
        evidence=s.evidence,
        conditions_met=s.conditions,
        explanation=(
            "The obstacle sensor stopped publishing: telemetry shows a gap far "
            "beyond the normal update interval, after which the planner degraded "
            "to a conservative mode and the task could not be completed safely."
        ),
        recommended_actions=[
            "Check lidar power, cabling, and driver logs at the dropout timestamp",
            "Inspect /diagnostics for the sensor node's last heartbeat",
            "Verify that the sensor watchdog stops the robot within its "
            "required latency budget",
            "Add alerting on sensor staleness before task-level failures occur",
        ],
    )


ALL_RULES = (
    rule_persistent_obstacle,
    rule_localization_failure,
    rule_controller_oscillation,
    rule_sensor_dropout,
)
