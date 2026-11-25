"""Example BlackBox analysis rule: sensor flap.

Catches the failure mode *before* a hard dropout: diagnostics raise
repeated stale-sensor warnings while the sensor keeps (mostly)
publishing — a loose cable, an overheating lidar, a saturating network
switch. The built-in sensor-dropout rule needs a sustained gap in
updates; this one fires on the flapping pattern that precedes it.

It maps to the same sensor_dropout category as the built-in, so when
both fire on a hard dropout the diagnosis is identical either way —
the example can compete without ever changing an outcome, which makes
it a safe template to copy.

Enable it without forking BlackBox:

    export PYTHONPATH=examples/rules
    export BLACKBOX_EXTRA_RULES=sensor_flap:sensor_flap
"""

from __future__ import annotations

from blackbox_api.analysis.features import IncidentFeatures
from blackbox_api.analysis.rules import RuleResult
from blackbox_api.analysis.thresholds import AnalysisThresholds
from blackbox_api.schemas import EvidenceItem, FailureCategory

#: Stale-sensor warnings at or above this count look like flapping.
MIN_WARNINGS = 3


def sensor_flap(
    features: IncidentFeatures, thresholds: AnalysisThresholds
) -> RuleResult:
    conditions: list[str] = []
    evidence: list[EvidenceItem] = []
    score = 0.0

    warnings = features.sensor_stale_warning_ts
    flapping = len(warnings) >= MIN_WARNINGS
    if flapping:
        score += 0.40
        conditions.append(f"stale_warnings>={MIN_WARNINGS}")
        evidence.append(EvidenceItem(
            id="flap-warnings",
            summary=(
                f"Diagnostics raised {len(warnings)} stale-sensor "
                f"warnings between t={warnings[0]:.1f} s and "
                f"t={warnings[-1]:.1f} s"
            ),
            detail="Repeated staleness without a sustained outage is "
            "the signature of an intermittent connection, not a dead "
            "sensor.",
            t=warnings[0],
            t_end=warnings[-1],
            tags=["sensor", "diagnostics", "flapping"],
        ))

    # The built-in dropout rule's gap test, inverted: updates kept
    # flowing. Uses the deployment's own tuned thresholds.
    median = features.obstacle_median_gap
    no_hard_gap = (
        median is not None
        and median > 0
        and features.obstacle_max_gap
        <= max(
            thresholds.sensor_gap_factor * median,
            thresholds.sensor_gap_min_s,
        )
    )
    if flapping and no_hard_gap:
        score += 0.30
        conditions.append("no_sustained_dropout")
        evidence.append(EvidenceItem(
            id="flap-no-gap",
            summary=(
                f"Sensor updates continued through the warnings "
                f"(largest gap {features.obstacle_max_gap:.1f} s against "
                f"a normal interval of {median:.1f} s)"
            ),
            t=warnings[0],
            tags=["sensor"],
        ))

    if flapping and "degraded" in features.planner_states:
        score += 0.15
        conditions.append("planner_degraded")
        evidence.append(EvidenceItem(
            id="flap-degraded",
            summary="Planner dropped to a degraded mode while the "
            "sensor flapped",
            t=warnings[0],
            tags=["planner", "degraded"],
        ))

    if flapping and (features.task_failed or features.timed_out):
        score += 0.15
        conditions.append("task_not_completed")

    return RuleResult(
        rule_id="example_sensor_flap",
        category=FailureCategory.SENSOR_DROPOUT,
        score=round(score, 3),
        evidence=evidence,
        conditions_met=conditions,
        explanation=(
            "Diagnostics flagged the obstacle sensor as stale repeatedly "
            "while updates kept arriving — an intermittent sensor "
            "connection degrading navigation before any hard dropout."
        ),
        recommended_actions=[
            "Inspect the sensor's cabling, connector seating, and power "
            "draw before it fails outright",
            "Check driver and network-switch logs for resets at the "
            "warning timestamps",
            "Alert on repeated staleness warnings so flapping sensors "
            "are serviced before they strand a robot",
        ],
    )
