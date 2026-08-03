#!/usr/bin/env python3
"""Seed the BlackBox database with the deterministic sample incidents.

Regenerates the sample-incident JSON files, then ingests each one through the
normal ingestion pipeline (validation + persistence + analysis).

Usage:  python scripts/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "sample-data"))

import generate  # noqa: E402  (packages/sample-data/generate.py)

from blackbox_api.ingestion.service import ingest_incident  # noqa: E402
from blackbox_api.logging import configure_logging  # noqa: E402
from blackbox_api.storage.db import init_db, session_scope  # noqa: E402


def main() -> int:
    configure_logging()
    generate.main()
    init_db()

    incident_dir = REPO_ROOT / "packages" / "sample-data" / "incidents"
    files = sorted(incident_dir.glob("INC-*.json"))
    if not files:
        print("no incident files found — generation failed?", file=sys.stderr)
        return 1

    with session_scope() as session:
        for path in files:
            incident, analysis = ingest_incident(
                session, path.read_bytes(), path.name
            )
            print(
                f"seeded {incident.id}: {analysis.failure_category.value} "
                f"(confidence {analysis.confidence:.0%}, "
                f"{len(analysis.evidence)} evidence items)"
            )
    print(f"done — {len(files)} incidents seeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
