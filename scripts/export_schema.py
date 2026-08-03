#!/usr/bin/env python3
"""Export the canonical incident schema as JSON Schema.

Writes packages/schemas/incident.schema.json from the Pydantic models so
non-Python consumers can validate incidents against the same contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from blackbox_api.schemas import AnalysisResult, Incident

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "packages" / "schemas" / "incident.schema.json"


def main() -> None:
    _, top = models_json_schema(
        [(Incident, "validation"), (AnalysisResult, "validation")],
        title="BlackBox incident schema",
    )
    OUT.write_text(json.dumps(top, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
