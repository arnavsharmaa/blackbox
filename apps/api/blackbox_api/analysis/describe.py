"""Introspection of the loaded analysis rules.

Powers the rules transparency surfaces (`/api/rules`, `blackbox rules`,
the web UI): every deployment can see exactly which deterministic rules
diagnose its incidents, built-in and plug-in alike.

Metadata comes from probing each rule once with empty features — rules
are pure functions over (features, thresholds), so an empty probe safely
yields the rule's identity, category, explanation, and runbook without
touching any incident data. A plug-in that cannot handle empty features
is still listed, from its function name alone.
"""

from __future__ import annotations

import inspect

from pydantic import BaseModel, ConfigDict

from blackbox_api.analysis.features import IncidentFeatures
from blackbox_api.analysis.plugins import RuleFn, get_all_rules
from blackbox_api.analysis.rules import ALL_RULES, RuleResult
from blackbox_api.analysis.thresholds import get_thresholds
from blackbox_api.schemas import FailureCategory


class RuleInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    #: None only for a plug-in that failed the metadata probe.
    category: FailureCategory | None
    builtin: bool
    #: Importable location, e.g. blackbox_api.analysis.rules:rule_sensor_dropout.
    source: str
    description: str
    explanation: str
    recommended_actions: list[str]


def _probe(rule: RuleFn) -> RuleResult | None:
    try:
        result = rule(IncidentFeatures(duration_s=0.0), get_thresholds())
    except Exception:  # noqa: BLE001 — a broken plug-in must not 500 the API
        return None
    return result if isinstance(result, RuleResult) else None


def describe_rules() -> list[RuleInfo]:
    builtins = set(ALL_RULES)
    infos = []
    for rule in get_all_rules():
        result = _probe(rule)
        infos.append(RuleInfo(
            rule_id=result.rule_id if result else rule.__name__,
            category=result.category if result else None,
            builtin=rule in builtins,
            source=f"{rule.__module__}:{rule.__name__}",
            description=inspect.getdoc(rule) or "",
            explanation=result.explanation if result else "",
            recommended_actions=(
                result.recommended_actions if result else []
            ),
        ))
    return infos
