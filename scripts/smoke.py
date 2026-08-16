#!/usr/bin/env python3
"""End-to-end smoke test against a running BlackBox stack.

Requires the app to be up (``make demo`` in another shell). Walks the demo
flow through real HTTP: health, incident list, primary incident detail,
telemetry needed by the replay, analysis with evidence, report, and the
GitHub issue preview. Exits non-zero on the first failure.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("BLACKBOX_API_URL", "http://localhost:8000")
WEB = os.environ.get("BLACKBOX_WEB_URL", "http://localhost:3000")
PRIMARY = "INC-2026-0728-001"

failures: list[str] = []


def get(url: str, *, as_json: bool = True) -> object:
    with urllib.request.urlopen(url, timeout=15) as response:
        body = response.read()
    return json.loads(body) if as_json else body.decode(errors="replace")


def check(label: str, condition: bool) -> None:
    status = "ok " if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        failures.append(label)


def main() -> int:
    try:
        health = get(f"{API}/health")
    except (urllib.error.URLError, OSError) as exc:
        print(f"API unreachable at {API}: {exc}", file=sys.stderr)
        return 1
    assert isinstance(health, dict)
    check("API health", health.get("status") == "ok")
    check("database seeded", int(health.get("incidents", 0)) >= 4)

    incidents = get(f"{API}/api/incidents")
    assert isinstance(incidents, dict)
    check("incident list has 4+ incidents", incidents["total"] >= 4)
    categories = {
        item.get("failure_category") for item in incidents["items"]
    }
    check(
        "four distinct diagnoses",
        {
            "persistent_obstacle",
            "localization_failure",
            "controller_oscillation",
            "sensor_dropout",
        }
        <= categories,
    )

    detail = get(f"{API}/api/incidents/{PRIMARY}")
    assert isinstance(detail, dict)
    incident = detail["incident"]
    channels = {series["channel"] for series in incident["telemetry"]}
    check(
        "primary incident replay channels present",
        {"pos_x", "pos_y", "linear_velocity", "obstacle_distance",
         "goal_distance", "localization_confidence"} <= channels,
    )
    check("primary incident has events", len(incident["events"]) >= 50)
    failure_events = [
        event
        for event in incident["events"]
        if event["event_type"] in ("task_timed_out", "task_failed")
    ]
    check("failure moment exists for jump-to-failure", len(failure_events) > 0)

    analysis = get(f"{API}/api/incidents/{PRIMARY}/analysis")
    assert isinstance(analysis, dict)
    check(
        "primary diagnosis is persistent_obstacle",
        analysis["failure_category"] == "persistent_obstacle",
    )
    check("analysis has evidence with timestamps",
          all("t" in item for item in analysis["evidence"])
          and len(analysis["evidence"]) >= 4)

    diff = get(f"{API}/api/incidents/{PRIMARY}/diff/INC-2026-0721-BASE")
    assert isinstance(diff, dict)
    check(
        "diff pins first divergence on obstacle_distance",
        diff["first_divergence_channel"] == "obstacle_distance"
        and diff["first_divergence_t"] is not None,
    )

    report = get(f"{API}/api/incidents/{PRIMARY}/report")
    assert isinstance(report, dict)
    check("report has markdown", "# Incident Report" in report["markdown"])

    issue = get(f"{API}/api/incidents/{PRIMARY}/github-issue?repo=acme/robots")
    assert isinstance(issue, dict)
    check("github issue prefill URL", str(issue["issue_url"]).startswith(
        "https://github.com/acme/robots/issues/new?"))
    check("github issue body sections",
          "## Steps to reproduce" in issue["body"]
          and "## Evidence" in issue["body"])

    bad = None
    try:
        request = urllib.request.Request(
            f"{API}/api/incidents/upload",
            data=(
                b"--x\r\nContent-Disposition: form-data; name=\"file\"; "
                b"filename=\"bad.json\"\r\nContent-Type: application/json"
                b"\r\n\r\n{oops\r\n--x--\r\n"
            ),
            headers={"Content-Type": "multipart/form-data; boundary=x"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as exc:
        bad = exc
    check("invalid upload rejected with 422",
          bad is not None and bad.code == 422)

    for path, label in [
        ("/", "web overview page"),
        (f"/incidents/{PRIMARY}", "web incident detail page"),
        (f"/incidents/{PRIMARY}/report", "web report page"),
        (f"/incidents/{PRIMARY}/issue", "web issue page"),
    ]:
        try:
            html = get(f"{WEB}{path}", as_json=False)
            assert isinstance(html, str)
            check(label, "BlackBox" in html)
        except (urllib.error.URLError, OSError) as exc:
            check(f"{label} ({exc})", False)

    print()
    if failures:
        print(f"{len(failures)} smoke check(s) failed", file=sys.stderr)
        return 1
    print("all smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
