"""Deterministic root-cause analysis engine.

Runs every rule over the incident's derived features, selects the highest
scoring category, and packages evidence, alternatives, and recommendations.
The AI explanation layer (blackbox_api.ai) may later *summarize* this result,
but never changes it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from blackbox_api.analysis.features import compute_features
from blackbox_api.analysis.rules import ALL_RULES, RuleResult
from blackbox_api.schemas import (
    AlternativeCause,
    AnalysisResult,
    FailureCategory,
    Incident,
)

ENGINE_VERSION = "1.0.0"

# A rule must reach this score before we claim its category as the root cause.
DIAGNOSIS_THRESHOLD = 0.5
# Alternatives below this score are noise and omitted.
ALTERNATIVE_FLOOR = 0.1
# Even a perfect rule match is reported below certainty: rules are heuristics.
CONFIDENCE_CEILING = 0.95


def analyze_incident(incident: Incident) -> AnalysisResult:
    features = compute_features(incident)
    results: list[RuleResult] = [rule(features) for rule in ALL_RULES]
    results.sort(key=lambda r: r.score, reverse=True)

    top = results[0]
    if top.score >= DIAGNOSIS_THRESHOLD:
        category = top.category
        confidence = round(top.score * CONFIDENCE_CEILING, 3)
        explanation = top.explanation
        recommended = top.recommended_actions
        evidence = top.evidence
        rules_triggered = [r.rule_id for r in results if r.score >= DIAGNOSIS_THRESHOLD]
    else:
        category = FailureCategory.UNKNOWN
        confidence = round(1.0 - top.score, 3)
        explanation = (
            "No deterministic rule matched this incident with sufficient "
            f"confidence (best candidate: {top.category.value} at "
            f"{top.score:.0%}). Manual review of the timeline is recommended."
        )
        recommended = [
            "Review the event timeline manually around the final error",
            "Compare telemetry against a known-good run of the same task",
            "If this failure mode recurs, add a detection rule for it",
        ]
        evidence = top.evidence
        rules_triggered = []

    alternatives = [
        AlternativeCause(
            category=r.category,
            score=r.score,
            reason=(
                f"Conditions met: {', '.join(r.conditions_met)}"
                if r.conditions_met
                else "No conditions met"
            ),
        )
        for r in results[1:]
        if r.score >= ALTERNATIVE_FLOOR
    ]

    return AnalysisResult(
        incident_id=incident.id,
        engine_version=ENGINE_VERSION,
        failure_category=category,
        confidence=confidence,
        explanation=explanation,
        recommended_actions=recommended,
        evidence=evidence,
        alternative_causes=alternatives,
        rules_triggered=rules_triggered,
        analyzed_at=datetime.now(UTC),
    )
