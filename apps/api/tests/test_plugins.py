from __future__ import annotations

from collections.abc import Iterator

import pytest

from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.analysis.plugins import (
    RulePluginError,
    get_all_rules,
    reset_rules_cache,
)
from blackbox_api.analysis.rules import ALL_RULES
from blackbox_api.schemas import FailureCategory, Incident


@pytest.fixture(autouse=True)
def clean_rules_cache() -> Iterator[None]:
    reset_rules_cache()
    yield
    reset_rules_cache()


def test_no_config_means_builtin_rules_only() -> None:
    assert get_all_rules() == tuple(ALL_RULES)


def _quiet_incident() -> Incident:
    """An incident no built-in rule scores highly on."""
    return Incident.model_validate({
        "id": "INC-QUIET-001",
        "robot_id": "W-900",
        "robot_model": "TestBot",
        "facility": "Test Facility",
        "task_name": "Idle check",
        "task_goal": "Stand still",
        "start_time": "2026-07-01T10:00:00Z",
        "end_time": "2026-07-01T10:01:00Z",
        "outcome": "failed",
        "severity": "warning",
        "software_version": "1.0.0",
        "map_version": "map-1",
        "environment": "test",
        "summary": "Failure with no strong rule signals",
        "events": [{
            "timestamp": "2026-07-01T10:00:59Z",
            "event_type": "task_failed",
            "subsystem": "task_manager",
            "severity": "error",
            "message": "failed for unclear reasons",
        }],
        "telemetry": [],
    })


def test_custom_rule_competes_and_wins(
    parsed_incidents: dict[str, Incident],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "BLACKBOX_EXTRA_RULES", "custom_rule_fixture:always_sensor_dropout"
    )
    reset_rules_cache()
    assert len(get_all_rules()) == len(ALL_RULES) + 1

    # On a quiet incident no built-in rule clears the threshold, so the
    # 0.99-scoring plug-in wins the diagnosis outright.
    analysis = analyze_incident(_quiet_incident())
    assert analysis.failure_category == FailureCategory.SENSOR_DROPOUT
    assert "custom_always_sensor_dropout" in analysis.rules_triggered
    assert analysis.explanation == "Diagnosed by the custom plug-in rule."

    # On the obstacle incident the built-in rule's perfect score still wins,
    # but the plug-in shows up among the triggered rules.
    obstacle = analyze_incident(parsed_incidents["obstacle"])
    assert obstacle.failure_category == FailureCategory.PERSISTENT_OBSTACLE
    assert "custom_always_sensor_dropout" in obstacle.rules_triggered


def test_invalid_spec_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLACKBOX_EXTRA_RULES", "not-a-valid-spec")
    reset_rules_cache()
    with pytest.raises(RulePluginError, match="module:function"):
        get_all_rules()


def test_missing_module_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLACKBOX_EXTRA_RULES", "no_such_module:rule")
    reset_rules_cache()
    with pytest.raises(RulePluginError, match="no_such_module"):
        get_all_rules()


def test_non_callable_attr_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLACKBOX_EXTRA_RULES", "custom_rule_fixture:__doc__")
    reset_rules_cache()
    with pytest.raises(RulePluginError, match="not a callable"):
        get_all_rules()


def test_rule_returning_wrong_type_is_rejected(
    parsed_incidents: dict[str, Incident],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "BLACKBOX_EXTRA_RULES", "custom_rule_fixture:not_a_rule_result"
    )
    reset_rules_cache()
    with pytest.raises(TypeError, match="expected RuleResult"):
        analyze_incident(parsed_incidents["obstacle"])
