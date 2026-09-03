from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest
from fastapi.testclient import TestClient

from blackbox_api.config import get_settings


@pytest.fixture()
def webhook_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, list[Any]]:
    monkeypatch.setenv("BLACKBOX_WEBHOOK_URL", "http://hooks.test/blackbox")
    get_settings.cache_clear()
    calls: list[Any] = []

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: float = 0) -> _Response:
        calls.append(request)
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return client, calls


def _upload(client: TestClient, sample: dict[str, Any]) -> None:
    response = client.post(
        "/api/incidents/upload",
        files={
            "file": (
                "incident.json",
                json.dumps(sample).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text


def test_webhook_fires_on_ingest(
    webhook_client: tuple[TestClient, list[Any]],
    sample_incidents: dict[str, dict[str, Any]],
) -> None:
    client, calls = webhook_client
    _upload(client, sample_incidents["obstacle"])

    assert len(calls) == 1
    request = calls[0]
    assert request.full_url == "http://hooks.test/blackbox"
    payload = json.loads(request.data.decode())
    assert payload["incident_id"] == "INC-2026-0728-001"
    assert payload["failure_category"] == "persistent_obstacle"
    assert "W-104" in payload["text"]


def test_webhook_failure_does_not_fail_ingest(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_incidents: dict[str, dict[str, Any]],
) -> None:
    monkeypatch.setenv("BLACKBOX_WEBHOOK_URL", "http://hooks.test/down")
    get_settings.cache_clear()

    def broken_urlopen(request: Any, timeout: float = 0) -> Any:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", broken_urlopen)
    _upload(client, sample_incidents["obstacle"])  # asserts 201


def test_no_webhook_configured_means_no_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_incidents: dict[str, dict[str, Any]],
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: calls.append(a)
    )
    _upload(client, sample_incidents["obstacle"])
    assert calls == []
