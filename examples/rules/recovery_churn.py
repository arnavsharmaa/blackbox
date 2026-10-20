"""Example BlackBox analysis rule: recovery churn.

Flags runs where the robot burned several recovery behaviors while
barely moving — thrashing in place — even when obstacle clearance never
crossed the facility's safety threshold (so the built-in obstacle rule
may not fire). Maps to the persistent-obstacle category: in practice
this pattern is almost always something physically in the way that the
lidar underestimates (low pallet lips, dangling shrink-wrap).

Enable it without forking BlackBox:

    export PYTHONPATH=examples/rules
    export BLACKBOX_EXTRA_RULES=recovery_churn:recovery_churn

A rule is a plain function (features, thresholds) -> RuleResult. It
competes with the built-ins on equal footing: highest score above the
diagnosis threshold wins. Scores must stay in [0, 1]; return 0 when the
pattern is absent rather than omitting conditions.
"""

from __future__ import annotations

from blackbox_api.analysis.features import IncidentFeatures
from blackbox_api.analysis.rules import RuleResult
from blackbox_api.analysis.thresholds import AnalysisThresholds
from blackbox_api.schemas import EvidenceItem, FailureCategory

#: Recoveries at or above this count start to look like churn.
MIN_RECOVERIES = 3
#: Total displacement across recoveries below this is "barely moving".
MAX_CHURN_DISPLACEMENT_M = 0.5


def recovery_churn(
    features: IncidentFeatures, thresholds: AnalysisThresholds
) -> RuleResult:
    conditions: list[str] = []
    evidence: list[EvidenceItem] = []
    score = 0.0

    recoveries = features.recoveries
    if len(recoveries) >= MIN_RECOVERIES:
        score += 0.4
        conditions.append(f"recovery_attempts>={MIN_RECOVERIES}")
        first = recoveries[0]
        evidence.append(EvidenceItem(
            id="churn-recoveries",
            summary=(
                f"{len(recoveries)} recovery behaviors ran without "
                f"restoring progress"
            ),
            t=first.t_start,
            t_end=recoveries[-1].t_end,
            tags=["recovery", "custom"],
        ))

    displacement = features.displacement_during_recoveries
    if (
        displacement is not None
        and displacement < MAX_CHURN_DISPLACEMENT_M
        and recoveries
    ):
        score += 0.4
        conditions.append(
            f"displacement_during_recoveries<{MAX_CHURN_DISPLACEMENT_M}"
        )
        evidence.append(EvidenceItem(
            id="churn-displacement",
            summary=(
                f"Robot moved only {displacement:.2f} m across all "
                f"recovery behaviors"
            ),
            t=recoveries[0].t_start,
            tags=["recovery", "custom"],
        ))

    if features.timed_out or features.task_failed:
        score += 0.2
        conditions.append("task_did_not_complete")

    return RuleResult(
        rule_id="recovery_churn",
        category=FailureCategory.PERSISTENT_OBSTACLE,
        score=min(score, 1.0),
        evidence=evidence,
        explanation=(
            "The robot repeatedly ran recovery behaviors while barely "
            "moving — thrashing in place, which almost always means a "
            "physical obstruction the range sensor underestimates."
        ),
        recommended_actions=[
            "Walk the location for low or thin obstructions (pallet "
            "lips, shrink-wrap, cables) the lidar plane can miss",
            "Review the recovery-behavior sequence; repeated "
            "rotate/backup cycles with no displacement waste the "
            "task budget",
        ],
        conditions_met=conditions,
    )
