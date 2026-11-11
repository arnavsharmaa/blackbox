from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from blackbox_api.api.ratelimit import reset_rate_limiter
from blackbox_api.config import get_settings


@pytest.fixture(autouse=True)
def _clean_limiter() -> None:
    reset_rate_limiter()
    yield
    reset_rate_limiter()


def _upload(client: TestClient, payload: dict[str, Any]) -> int:
    return client.post(
        "/api/incidents/upload",
        files={
            "file": (
                "incident.json",
                json.dumps(payload).encode(),
                "application/json",
            )
        },
    ).status_code


def test_writes_unlimited_by_default(
    client: TestClient, sample_incidents: dict[str, dict[str, Any]]
) -> None:
    for _ in range(5):
        assert _upload(client, sample_incidents["obstacle"]) == 201


def test_write_limit_enforced_with_retry_after(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_incidents: dict[str, dict[str, Any]],
) -> None:
    monkeypatch.setenv("BLACKBOX_RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()

    for _ in range(3):
        assert _upload(client, sample_incidents["obstacle"]) == 201
    response = client.post(
        "/api/incidents/upload",
        files={"file": ("x.json", b"{}", "application/json")},
    )
    assert response.status_code == 429
    assert "rate limit exceeded" in response.json()["detail"]
    assert int(response.headers["Retry-After"]) >= 1

    # Reads are never limited.
    for _ in range(5):
        assert client.get("/api/incidents").status_code == 200
