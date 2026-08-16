from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "packages" / "sample-data"))

import generate  # noqa: E402

from blackbox_api.schemas import Incident  # noqa: E402


@pytest.fixture(scope="session")
def sample_incidents() -> dict[str, dict]:
    """Raw sample-incident dicts keyed by a short name."""
    incidents = generate.generate_all()
    return {
        "obstacle": incidents[0],
        "localization": incidents[1],
        "oscillation": incidents[2],
        "sensor_dropout": incidents[3],
        "baseline": incidents[4],
    }


@pytest.fixture(scope="session")
def parsed_incidents(sample_incidents: dict[str, dict]) -> dict[str, Incident]:
    return {
        name: Incident.model_validate(raw)
        for name, raw in sample_incidents.items()
    }


@pytest.fixture()
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """TestClient backed by a fresh temporary SQLite database."""
    from blackbox_api.config import get_settings
    from blackbox_api.storage import db as db_module

    monkeypatch.setenv(
        "BLACKBOX_DATABASE_URL", f"sqlite:///{tmp_path}/test.db"
    )
    get_settings.cache_clear()
    db_module.reset_engine_for_tests()

    from blackbox_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    db_module.reset_engine_for_tests()


@pytest.fixture()
def seeded_client(
    client: TestClient, sample_incidents: dict[str, dict]
) -> TestClient:
    """Client whose database contains all the sample incidents."""
    import json

    for raw in sample_incidents.values():
        response = client.post(
            "/api/incidents/upload",
            files={
                "file": (
                    f"{raw['id']}.json",
                    json.dumps(raw).encode(),
                    "application/json",
                )
            },
        )
        assert response.status_code == 201, response.text
    return client
