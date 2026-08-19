"""Guards the committed OpenAPI spec against drifting from the app.

Compares only paths and their methods — the parts that are stable across
FastAPI versions — so adding or removing an endpoint without re-running
`make openapi` fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

from blackbox_api.main import create_app

SPEC_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "openapi.json"
)


def _routes(spec: dict) -> set[tuple[str, str]]:
    return {
        (path, method)
        for path, operations in spec["paths"].items()
        for method in operations
    }


def test_committed_spec_matches_app_routes() -> None:
    committed = json.loads(SPEC_PATH.read_text())
    live = create_app().openapi()
    assert _routes(committed) == _routes(live), (
        "docs/openapi.json is stale — run `make openapi` and commit the result"
    )
