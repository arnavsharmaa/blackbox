#!/usr/bin/env python3
"""Export the REST API's OpenAPI spec.

Writes docs/openapi.json from the FastAPI app so API consumers can
generate clients or diff the contract without running a server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Works without an installed blackbox-api package (e.g. plain `python3`).
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from blackbox_api.main import create_app  # noqa: E402

OUT = REPO_ROOT / "docs" / "openapi.json"


def main() -> None:
    spec = create_app().openapi()
    OUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
