# Writing analysis rules

Every root cause BlackBox reports comes from a deterministic rule — a
plain Python function, no LLM. Deployments add their own rules without
forking: this guide covers the contract, the features you can score
against, and how to ship and verify a rule.

A test-covered, copyable example lives in
[examples/rules](../examples/rules).

## The contract

```python
from blackbox_api.analysis.features import IncidentFeatures
from blackbox_api.analysis.rules import RuleResult
from blackbox_api.analysis.thresholds import AnalysisThresholds
from blackbox_api.schemas import EvidenceItem, FailureCategory


def my_rule(
    features: IncidentFeatures, thresholds: AnalysisThresholds
) -> RuleResult:
    ...
```

- The function must be importable (`PYTHONPATH`) and listed in
  `BLACKBOX_EXTRA_RULES` as `module:function`; several specs are
  comma-separated.
- It must return a `RuleResult` with a `score` in `[0, 1]` — return a
  low or zero score when the pattern is absent, never raise.
- `category` must be one of the canonical `FailureCategory` values.
  Categories are a closed set shared by the schema, the UI, analytics,
  and calibration; a genuinely new failure mode belongs in the main
  engine — open an issue.
- Rules must be deterministic: same incident in, same result out.
  Don't consult the network, the clock, or anything random.

## How scoring works

All rules — built-in and plug-in — run on every analyzed incident and
compete on equal footing:

- The highest score **at or above 0.5** (`DIAGNOSIS_THRESHOLD`) becomes
  the diagnosis; below that the incident is categorized `unknown`.
- Other rules scoring **above 0.1** (`ALTERNATIVE_FLOOR`) are reported
  as alternative causes with their scores.
- Reported confidence is **capped at 0.95** (`CONFIDENCE_CEILING`):
  rules are heuristics and the product never claims certainty.

The built-ins compose a score from independently weighted conditions
(weights summing to 1.0) so that partial matches score partially; copy
that structure rather than returning only 0 or 1.

## Features you can score against

`IncidentFeatures` is computed once per incident from its events and
telemetry ([features.py](../apps/api/blackbox_api/analysis/features.py)
is authoritative). Fields:

| Group | Fields |
| --- | --- |
| Run shape | `duration_s`, `timed_out`, `task_failed`, `timeout_t`, `failure_t`, `goal_issued`, `goal_active_at_end` |
| Velocity commands | `zero_cmd_streak`, `zero_cmd_streak_t`, `zero_cmd_total` |
| Obstacle clearance | `obstacle_low_interval`, `obstacle_min` |
| Motion | `total_displacement`, `displacement_during_recoveries` |
| Recoveries | `recoveries` (list of `RecoveryAttempt` with `behavior`, `t_start`, `t_end`, `succeeded`) |
| Localization | `loc_conf_min`, `loc_conf_mean`, `loc_conf_max_drop`, `loc_conf_drop_t`, `max_pose_jump`, `max_pose_jump_t` |
| Controller | `angular_flips`, `angular_flip_window`, `progress_in_flip_window`, `mean_abs_linear_in_flip_window`, `replan_count` |
| Sensor freshness | `obstacle_median_gap`, `obstacle_max_gap`, `obstacle_max_gap_t`, `sensor_stale_warning_ts` |
| Planner | `planner_states` |

Many fields are `None` when the incident lacks the relevant telemetry —
guard every comparison. Thresholds (safety distances, streak minimums,
…) come from `AnalysisThresholds`, which operators tune per deployment
via environment variables ([configuration.md](configuration.md));
prefer `thresholds.<field>` over hard-coded constants so your rule
respects the same tuning.

## Evidence

Fill `RuleResult.evidence` with `EvidenceItem`s anchored to incident
timestamps (`t`, optional `t_end`, optional telemetry `channel`). The
replay UI renders each item as a clickable claim that seeks the replay
to that moment — evidence is how an engineer audits your rule, so
every condition that fired should leave one.

## Shipping a rule

```bash
export PYTHONPATH=/opt/blackbox-rules
export BLACKBOX_EXTRA_RULES=acme_rules:battery_sag,acme_rules:dock_misalign
```

With Docker Compose, mount the rules directory and set both variables
on the `api` service:

```yaml
services:
  api:
    volumes:
      - ./acme-rules:/opt/blackbox-rules:ro
    environment:
      PYTHONPATH: /opt/blackbox-rules
      BLACKBOX_EXTRA_RULES: acme_rules:battery_sag
```

A bad spec or unimportable module raises `RulePluginError` on first
analysis — check the API logs if diagnoses stop.

## Verifying it loaded

- `GET /api/rules` — every loaded rule with id, category, and source;
  plug-ins carry their `module:function` spec.
- `blackbox rules --verbose` — the same from a terminal.
- The web UI's **Rules** page — plug-ins are badged, and each rule
  links to the incidents it diagnosed.

## Testing your rule

Feed the engine a canonical incident JSON and assert on the result, the
way [test_example_rules.py](../apps/api/tests/test_example_rules.py)
exercises the shipped examples:

```python
from blackbox_api.analysis.engine import analyze_incident

def test_battery_sag_fires(monkeypatch):
    monkeypatch.setenv(
        "BLACKBOX_EXTRA_RULES", "acme_rules:battery_sag"
    )
    reset_rules_cache()
    result = analyze_incident(sagging_incident())
    assert result.failure_category is FailureCategory.UNKNOWN  # or yours
    assert any(e.id.startswith("sag-") for e in result.evidence)
```
