from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from blackbox_api.config import get_settings


@pytest.fixture()
def tokened_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    """The regular test client with two API tokens configured."""
    monkeypatch.setenv("BLACKBOX_API_TOKENS", "sekret-1, sekret-2")
    get_settings.cache_clear()
    return client


def test_api_is_open_without_configured_tokens(client: TestClient) -> None:
    assert client.get("/api/incidents").status_code == 200


def test_missing_token_is_rejected(tokened_client: TestClient) -> None:
    response = tokened_client.get("/api/incidents")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "missing API token" in response.json()["detail"]


def test_wrong_token_is_rejected(tokened_client: TestClient) -> None:
    response = tokened_client.get(
        "/api/incidents", headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401
    assert "invalid API token" in response.json()["detail"]


def test_bearer_token_is_accepted(tokened_client: TestClient) -> None:
    response = tokened_client.get(
        "/api/incidents", headers={"Authorization": "Bearer sekret-1"}
    )
    assert response.status_code == 200


def test_any_configured_token_works_via_x_api_key(
    tokened_client: TestClient,
) -> None:
    response = tokened_client.get(
        "/api/analytics", headers={"X-API-Key": "sekret-2"}
    )
    assert response.status_code == 200


def test_health_stays_open_with_tokens(tokened_client: TestClient) -> None:
    assert tokened_client.get("/health").status_code == 200


def test_readonly_token_reads_but_cannot_write(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLACKBOX_API_TOKENS", "sekret-1")
    monkeypatch.setenv("BLACKBOX_READONLY_TOKENS", "viewer-1")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer viewer-1"}

    assert client.get("/api/incidents", headers=headers).status_code == 200
    assert client.get("/api/analytics", headers=headers).status_code == 200

    denied = client.delete("/api/incidents/INC-X", headers=headers)
    assert denied.status_code == 403
    assert "read-only" in denied.json()["detail"]
    assert (
        client.post(
            "/api/incidents/upload",
            headers=headers,
            files={"file": ("x.json", b"{}", "application/json")},
        ).status_code
        == 403
    )


def test_readonly_tokens_alone_still_enable_auth(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLACKBOX_READONLY_TOKENS", "viewer-1")
    get_settings.cache_clear()
    assert client.get("/api/incidents").status_code == 401
    assert (
        client.get(
            "/api/incidents", headers={"X-API-Key": "viewer-1"}
        ).status_code
        == 200
    )


def test_writes_require_the_token_too(tokened_client: TestClient) -> None:
    assert (
        tokened_client.delete("/api/incidents/INC-NOPE").status_code == 401
    )
    assert (
        tokened_client.post(
            "/api/incidents/upload",
            files={"file": ("x.json", b"{}", "application/json")},
        ).status_code
        == 401
    )
