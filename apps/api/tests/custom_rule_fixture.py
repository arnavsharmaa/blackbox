"""A minimal custom analysis rule used by the plug-in tests."""

from __future__ import annotations

from blackbox_api.analysis.features import IncidentFeatures
from blackbox_api.analysis.rules import RuleResult
from blackbox_api.analysis.thresholds import AnalysisThresholds
from blackbox_api.schemas import EvidenceItem, FailureCategory


def always_sensor_dropout(
    features: IncidentFeatures, thresholds: AnalysisThresholds
) -> RuleResult:
    """Fires on every incident with a near-certain score (test fixture)."""
    return RuleResult(
        rule_id="custom_always_sensor_dropout",
        category=FailureCategory.SENSOR_DROPOUT,
        score=0.99,
        evidence=[
            EvidenceItem(
                id="custom-e1",
                summary="Custom plug-in rule fired",
                t=0.0,
                tags=["custom"],
            )
        ],
        explanation="Diagnosed by the custom plug-in rule.",
        recommended_actions=["Inspect via the custom runbook"],
        conditions_met=["always"],
    )


def not_a_rule_result(
    features: IncidentFeatures, thresholds: AnalysisThresholds
) -> str:
    return "not a RuleResult"
