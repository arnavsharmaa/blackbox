from __future__ import annotations

from blackbox_api.analysis.engine import DIAGNOSIS_THRESHOLD, analyze_incident
from blackbox_api.analysis.features import compute_features
from blackbox_api.schemas import FailureCategory, Incident


def test_persistent_obstacle_diagnosis(parsed_incidents: dict[str, Incident]) -> None:
    result = analyze_incident(parsed_incidents["obstacle"])
    assert result.failure_category == FailureCategory.PERSISTENT_OBSTACLE
    assert result.confidence >= DIAGNOSIS_THRESHOLD
    assert "persistent_obstacle_blockage" in result.rules_triggered
    summaries = " | ".join(e.summary for e in result.evidence)
    assert "Obstacle distance remained below" in summaries
    assert "zero-velocity commands" in summaries
    assert "recovery behaviors" in summaries
    assert "timed out" in summaries.lower()
    # Exculpatory evidence: localization stayed healthy.
    assert "Localization confidence remained above" in summaries
    # Every evidence item must carry a timestamp anchor within the incident.
    duration = parsed_incidents["obstacle"].duration_s
    for item in result.evidence:
        assert 0 <= item.t <= duration


def test_localization_failure_diagnosis(
    parsed_incidents: dict[str, Incident],
) -> None:
    result = analyze_incident(parsed_incidents["localization"])
    assert result.failure_category == FailureCategory.LOCALIZATION_FAILURE
    assert result.confidence >= DIAGNOSIS_THRESHOLD
    summaries = " | ".join(e.summary for e in result.evidence)
    assert "confidence" in summaries.lower()
    assert "jumped" in summaries


def test_controller_oscillation_diagnosis(
    parsed_incidents: dict[str, Incident],
) -> None:
    result = analyze_incident(parsed_incidents["oscillation"])
    assert result.failure_category == FailureCategory.CONTROLLER_OSCILLATION
    assert result.confidence >= DIAGNOSIS_THRESHOLD
    summaries = " | ".join(e.summary for e in result.evidence)
    assert "flipped sign" in summaries
    assert "re-planned" in summaries


def test_sensor_dropout_diagnosis(parsed_incidents: dict[str, Incident]) -> None:
    result = analyze_incident(parsed_incidents["sensor_dropout"])
    assert result.failure_category == FailureCategory.SENSOR_DROPOUT
    assert result.confidence >= DIAGNOSIS_THRESHOLD
    summaries = " | ".join(e.summary for e in result.evidence)
    assert "updates stopped" in summaries
    assert "degraded" in summaries.lower()


def test_diagnoses_are_distinct(parsed_incidents: dict[str, Incident]) -> None:
    categories = {
        analyze_incident(i).failure_category for i in parsed_incidents.values()
    }
    assert len(categories) == 4


def test_analysis_is_deterministic(parsed_incidents: dict[str, Incident]) -> None:
    a = analyze_incident(parsed_incidents["obstacle"])
    b = analyze_incident(parsed_incidents["obstacle"])
    assert a.model_dump(exclude={"analyzed_at"}) == b.model_dump(
        exclude={"analyzed_at"}
    )


def test_alternatives_exclude_winner(parsed_incidents: dict[str, Incident]) -> None:
    result = analyze_incident(parsed_incidents["obstacle"])
    assert result.failure_category not in {
        a.category for a in result.alternative_causes
    }


def test_features_obstacle_incident(parsed_incidents: dict[str, Incident]) -> None:
    f = compute_features(parsed_incidents["obstacle"])
    assert f.zero_cmd_streak >= 5
    assert f.obstacle_low_interval is not None
    assert f.obstacle_low_interval.duration >= 5.0
    assert f.obstacle_low_interval.min_value < 0.6
    assert len(f.recoveries) == 3
    assert not any(r.succeeded for r in f.recoveries)
    assert f.timed_out and f.task_failed
    assert f.loc_conf_min is not None and f.loc_conf_min >= 0.9


def test_features_sensor_gap(parsed_incidents: dict[str, Incident]) -> None:
    f = compute_features(parsed_incidents["sensor_dropout"])
    assert f.obstacle_max_gap >= 20.0
    assert f.obstacle_median_gap is not None
    assert f.obstacle_median_gap <= 1.0
    assert len(f.sensor_stale_warning_ts) >= 2
