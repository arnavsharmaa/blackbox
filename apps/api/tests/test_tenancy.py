from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from blackbox_api.config import get_settings

FREMONT = "Warehouse 3 — Fremont"
CHICAGO = "Warehouse 7 — Chicago"
PRIMARY = "INC-2026-0728-001"

FREMONT_TOK = {"Authorization": "Bearer fremont-tok"}
CHICAGO_TOK = {"Authorization": "Bearer chicago-tok"}
ADMIN_TOK = {"Authorization": "Bearer admin-tok"}


@pytest.fixture()
def tenants(
    seeded_client: TestClient,
    sample_incidents: dict[str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Five Fremont samples plus one Chicago incident, tokens per facility."""
    chicago = copy.deepcopy(sample_incidents["oscillation"])
    chicago["id"] = "INC-CHI-001"
    chicago["facility"] = CHICAGO
    response = seeded_client.post(
        "/api/incidents/upload",
        files={
            "file": (
                "chi.json",
                json.dumps(chicago).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text

    monkeypatch.setenv("BLACKBOX_API_TOKENS", "admin-tok")
    monkeypatch.setenv(
        "BLACKBOX_FACILITY_TOKENS",
        json.dumps({"fremont-tok": FREMONT, "chicago-tok": CHICAGO}),
    )
    get_settings.cache_clear()
    return seeded_client


def test_list_is_scoped_to_the_token_facility(tenants: TestClient) -> None:
    fremont = tenants.get("/api/incidents", headers=FREMONT_TOK).json()
    assert fremont["total"] == 5
    assert {i["facility"] for i in fremont["items"]} == {FREMONT}

    chicago = tenants.get("/api/incidents", headers=CHICAGO_TOK).json()
    assert chicago["total"] == 1
    assert chicago["items"][0]["id"] == "INC-CHI-001"

    # An explicit facility param cannot escape the token's scope.
    sneaky = tenants.get(
        "/api/incidents",
        headers=CHICAGO_TOK,
        params={"facility": FREMONT},
    ).json()
    assert sneaky["total"] == 1
    assert sneaky["items"][0]["facility"] == CHICAGO

    # Full tokens still see everything.
    assert tenants.get("/api/incidents", headers=ADMIN_TOK).json()["total"] == 6


def test_cross_facility_reads_look_missing(tenants: TestClient) -> None:
    assert (
        tenants.get(f"/api/incidents/{PRIMARY}", headers=CHICAGO_TOK).status_code
        == 404
    )
    for suffix in ("events", "telemetry", "analysis", "report", "github-issue"):
        assert (
            tenants.get(
                f"/api/incidents/{PRIMARY}/{suffix}", headers=CHICAGO_TOK
            ).status_code
            == 404
        ), suffix
    # The same requests succeed inside the token's own facility.
    assert (
        tenants.get(f"/api/incidents/{PRIMARY}", headers=FREMONT_TOK).status_code
        == 200
    )
    assert (
        tenants.get("/api/incidents/INC-CHI-001", headers=CHICAGO_TOK).status_code
        == 200
    )


def test_diff_cannot_cross_facilities(tenants: TestClient) -> None:
    response = tenants.get(
        f"/api/incidents/INC-CHI-001/diff/{PRIMARY}", headers=CHICAGO_TOK
    )
    assert response.status_code == 404
