#!/usr/bin/env python3
"""Export the canonical incident schema as JSON Schema.

Writes packages/schemas/incident.schema.json from the Pydantic models so
non-Python consumers can validate incidents against the same contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Works without an installed blackbox-api package (e.g. plain `python3`).
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from pydantic.json_schema import models_json_schema  # noqa: E402

from blackbox_api.schemas import AnalysisResult, Incident  # noqa: E402
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
