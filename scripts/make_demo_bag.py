#!/usr/bin/env python3
"""Generate a demo ROS 2 MCAP bag and print the upload command for it.

Writes packages/sample-data/demo-capture.mcap — a deterministic recording of
a robot getting blocked mid-navigation — so the rosbag2 ingestion path can be
exercised without a ROS installation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "sample-data"))

from ros2_bag_builder import build_blocked_run_bag  # noqa: E402

OUT = REPO_ROOT / "packages" / "sample-data" / "demo-capture.mcap"


def main() -> None:
    OUT.write_bytes(build_blocked_run_bag())
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(
        "\nUpload it with:\n\n"
        "curl -X POST http://localhost:8000/api/incidents/upload \\\n"
        f"  -F 'file=@{OUT.relative_to(REPO_ROOT)}' \\\n"
        "  -F 'metadata={\"id\": \"INC-BAG-DEMO-001\", \"robot_id\": \"W-104\","
        " \"facility\": \"Warehouse 3 — Fremont\"}'"
    )


if __name__ == "__main__":
    main()
