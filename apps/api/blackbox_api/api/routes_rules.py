"""The loaded analysis rules, for transparency and debugging.

BlackBox's root causes come from deterministic rules, never an LLM —
this endpoint lets any deployment verify exactly which rules are in
play, including custom plug-ins from BLACKBOX_EXTRA_RULES.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from blackbox_api.analysis.describe import RuleInfo, describe_rules
from blackbox_api.analysis.engine import (
    CONFIDENCE_CEILING,
    DIAGNOSIS_THRESHOLD,
    ENGINE_VERSION,
)

router = APIRouter(prefix="/api", tags=["rules"])


class RulesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: str
    #: A rule must reach this score to be claimed as the root cause.
    diagnosis_threshold: float
    #: Reported confidence never exceeds this: rules are heuristics.
    confidence_ceiling: float
    rules: list[RuleInfo]


@router.get("/rules", response_model=RulesResponse)
def get_rules() -> RulesResponse:
    """Every rule the engine runs, built-in and plug-in alike."""
    return RulesResponse(
        engine_version=ENGINE_VERSION,
        diagnosis_threshold=DIAGNOSIS_THRESHOLD,
        confidence_ceiling=CONFIDENCE_CEILING,
        rules=describe_rules(),
    )
