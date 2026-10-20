from __future__ import annotations

import sys
from pathlib import Path

import pytest

from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.analysis.features import compute_features
from blackbox_api.analysis.plugins import reset_rules_cache
from blackbox_api.schemas import Incident

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "rules"
sys.path.insert(0, str(EXAMPLES))

from recovery_churn import recovery_churn  # noqa: E402


@pytest.fixture(autouse=True)
def _rules_cache() -> None:
    reset_rules_cache()
    yield
    reset_rules_cache()


def test_recovery_churn_scores_the_thrashing_run(
    parsed_incidents: dict[str, Incident],
) -> None:
    from blackbox_api.analysis.thresholds import get_thresholds

    features = compute_features(parsed_incidents["obstacle"])
    result = recovery_churn(features, get_thresholds())
    assert result.score == 1.0
    assert "recovery_attempts>=3" in result.conditions_met
    assert result.evidence[0].t > 0

    quiet = compute_features(parsed_incidents["baseline"])
    assert recovery_churn(quiet, get_thresholds()).score == 0.0


def test_example_rule_loads_through_the_plugin_registry(
    parsed_incidents: dict[str, Incident],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "BLACKBOX_EXTRA_RULES", "recovery_churn:recovery_churn"
    )
    reset_rules_cache()
    analysis = analyze_incident(parsed_incidents["obstacle"])
    # The built-in obstacle rule still wins outright, but the example
    # competed and is reported alongside it.
    assert analysis.failure_category.value == "persistent_obstacle"
    assert "recovery_churn" in analysis.rules_triggered
