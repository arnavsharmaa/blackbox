# Example analysis rules

Working `BLACKBOX_EXTRA_RULES` plug-ins to copy from. Each rule is a
plain function `(IncidentFeatures, AnalysisThresholds) -> RuleResult`
that competes with the built-in rules on equal footing.

| Rule | Fires when | Category |
| --- | --- | --- |
| [`recovery_churn`](./recovery_churn.py) | ≥3 recovery behaviors with <0.5 m total displacement on an unfinished task | persistent_obstacle |

Run BlackBox with an example enabled:

```bash
PYTHONPATH=examples/rules BLACKBOX_EXTRA_RULES=recovery_churn:recovery_churn make api
```

Rules must map to an existing `FailureCategory`; the canonical schema
(and every consumer of it) treats categories as a closed set. A rule
that detects a genuinely new failure mode belongs in the main engine —
open an issue.

These examples are exercised by the test suite
(`apps/api/tests/test_example_rules.py`), so they cannot rot.
