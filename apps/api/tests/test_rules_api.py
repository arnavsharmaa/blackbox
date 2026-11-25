from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from blackbox_api.analysis.plugins import reset_rules_cache


@pytest.fixture(autouse=True)
def clean_rules_cache() -> Iterator[None]:
    reset_rules_cache()
    yield
    reset_rules_cache()


def test_rules_endpoint_lists_the_builtin_rules(client: TestClient) -> None:
    response = client.get("/api/rules")
    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"]
    assert 0 < body["diagnosis_threshold"] < 1
    assert body["diagnosis_threshold"] < body["confidence_ceiling"] <= 1

    rules = body["rules"]
    assert [r["rule_id"] for r in rules] == [
        "persistent_obstacle_blockage",
        "localization_failure",
        "controller_oscillation",
        "sensor_dropout",
    ]
    for rule in rules:
        assert rule["builtin"] is True
        assert rule["category"] is not None
        assert rule["source"].startswith("blackbox_api.analysis.rules:")
        assert rule["description"]
        assert rule["explanation"]
        assert rule["recommended_actions"]


def test_rules_endpoint_includes_plugins(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "BLACKBOX_EXTRA_RULES", "custom_rule_fixture:always_sensor_dropout"
    )
    reset_rules_cache()

    rules = client.get("/api/rules").json()["rules"]
    assert len(rules) == 5
    plugin = rules[-1]
    assert plugin["rule_id"] == "custom_always_sensor_dropout"
    assert plugin["builtin"] is False
    assert plugin["category"] == "sensor_dropout"
    assert plugin["source"] == "custom_rule_fixture:always_sensor_dropout"
