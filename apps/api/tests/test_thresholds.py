from __future__ import annotations

from collections.abc import Iterator

import pytest

from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.analysis.thresholds import (
    AnalysisThresholds,
    get_thresholds,
    reset_thresholds_cache,
)
from blackbox_api.schemas import FailureCategory, Incident


@pytest.fixture(autouse=True)
def clean_threshold_cache() -> Iterator[None]:
    reset_thresholds_cache()
    yield
    reset_thresholds_cache()


def test_defaults_match_original_engine_constants() -> None:
    th = AnalysisThresholds()
    assert th.obstacle_safety_threshold_m == 0.6
    assert th.zero_cmd_streak_min == 5
    assert th.recovery_attempts_min == 2
    assert th.loc_conf_fault == 0.5
    assert th.pose_jump_m == 1.0
    assert th.angular_flips_min == 8
    assert th.sensor_gap_factor == 5.0


def test_env_overrides_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOX_RULE_OBSTACLE_SAFETY_THRESHOLD_M", "0.9")
    monkeypatch.setenv("BLACKBOX_RULE_ANGULAR_FLIPS_MIN", "20")
    reset_thresholds_cache()
    th = get_thresholds()
    assert th.obstacle_safety_threshold_m == 0.9
    assert th.angular_flips_min == 20


def test_invalid_override_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOX_RULE_OBSTACLE_SAFETY_THRESHOLD_M", "-1")
    reset_thresholds_cache()
    with pytest.raises(Exception, match="obstacle_safety_threshold_m"):
        get_thresholds()


def test_thresholds_change_the_diagnosis(
    parsed_incidents: dict[str, Incident],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = analyze_incident(parsed_incidents["obstacle"])
    assert baseline.failure_category == FailureCategory.PERSISTENT_OBSTACLE

    # Demand an absurd zero-velocity streak: that condition can no longer be
    # met, so confidence must drop while the category holds.
    monkeypatch.setenv("BLACKBOX_RULE_ZERO_CMD_STREAK_MIN", "500")
    reset_thresholds_cache()
    tightened = analyze_incident(parsed_incidents["obstacle"])
    assert tightened.failure_category == FailureCategory.PERSISTENT_OBSTACLE
    assert tightened.confidence < baseline.confidence
    summaries = " | ".join(e.summary for e in tightened.evidence)
    assert "zero-velocity commands" not in summaries


def test_threshold_appears_in_evidence_text(
    parsed_incidents: dict[str, Incident],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A facility with wider clearance rules sees its own threshold quoted.
    monkeypatch.setenv("BLACKBOX_RULE_OBSTACLE_SAFETY_THRESHOLD_M", "0.75")
    reset_thresholds_cache()
    analysis = analyze_incident(parsed_incidents["obstacle"])
    summaries = " | ".join(e.summary for e in analysis.evidence)
    assert "below 0.75 m" in summaries
