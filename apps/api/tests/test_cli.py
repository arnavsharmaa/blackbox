from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from blackbox_api import cli


class FakeApi:
    """Records requests and returns canned responses per (method, path)."""

    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]):
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        path = url.split("localhost:8000", 1)[1].split("?", 1)[0]
        self.calls.append({
            "method": method, "url": url, "token": token,
            "body": body, "content_type": content_type,
        })
        return self.responses[(method, path)]


def test_list_renders_a_table(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeApi({("GET", "/api/incidents"): {
        "items": [{
            "id": "INC-1", "robot_id": "W-104", "outcome": "timed_out",
            "failure_category": "persistent_obstacle", "confidence": 0.95,
            "task_name": "Deliver pallet to Loading Bay B",
        }],
        "total": 5,
    }})
    monkeypatch.setattr(cli, "_request", fake)

    assert cli.main(["list", "--robot", "W-104"]) == 0
    out = capsys.readouterr().out
    assert "INC-1" in out
    assert "persistent_obstacle" in out
    assert "95%" in out
    assert "(1 of 5 incidents)" in out
    assert "robot_id=W-104" in fake.calls[0]["url"]


def test_show_prints_diagnosis_and_feedback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeApi({("GET", "/api/incidents/INC-1"): {
        "incident": {
            "id": "INC-1", "task_name": "Deliver",
            "robot_id": "W-104", "robot_model": "AMR", "facility": "W3",
            "start_time": "s", "end_time": "e",
            "outcome": "timed_out", "severity": "critical",
            "summary": "Blocked by a pallet.",
        },
        "analysis": {
            "failure_category": "persistent_obstacle", "confidence": 0.95,
            "explanation": "Blocked.",
            "evidence": [{"t": 31.0, "summary": "zero-velocity streak"}],
        },
        "feedback": {
            "verdict": "corrected", "actual_category": "sensor_dropout",
        },
    }})
    monkeypatch.setattr(cli, "_request", fake)

    assert cli.main(["show", "INC-1"]) == 0
    out = capsys.readouterr().out
    assert "persistent_obstacle (95% confidence)" in out
    assert "t=31.0s zero-velocity streak" in out
    assert "corrected (actually sensor_dropout)" in out


def test_upload_sends_multipart(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    incident_file = tmp_path / "incident.json"
    incident_file.write_text("{}")
    fake = FakeApi({("POST", "/api/incidents/upload"): {
        "incident_id": "INC-9", "failure_category": "sensor_dropout",
        "confidence": 0.9, "event_count": 12,
    }})
    monkeypatch.setattr(cli, "_request", fake)

    assert cli.main([
        "--token", "sekret", "upload", str(incident_file),
        "--metadata", '{"id": "INC-9"}',
    ]) == 0
    assert "INC-9: sensor_dropout (90% confidence, 12 events)" in (
        capsys.readouterr().out
    )
    call = fake.calls[0]
    assert call["token"] == "sekret"
    assert call["content_type"].startswith("multipart/form-data; boundary=")
    assert b'name="metadata"' in call["body"]
    assert b'filename="incident.json"' in call["body"]


def test_prune_refuses_without_yes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeApi({})
    monkeypatch.setattr(cli, "_request", fake)
    assert cli.main(["prune", "--days", "90"]) == 1
    assert "without --yes" in capsys.readouterr().err
    assert fake.calls == []


def test_prune_deletes_with_yes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeApi({("DELETE", "/api/incidents"): {
        "deleted": 2, "incident_ids": ["INC-A", "INC-B"],
    }})
    monkeypatch.setattr(cli, "_request", fake)
    assert cli.main([
        "prune", "--before", "2026-01-01T00:00:00Z", "--yes"
    ]) == 0
    out = capsys.readouterr().out
    assert "deleted 2 incident(s)" in out
    assert "INC-B" in out
    assert "before=2026-01-01" in fake.calls[0]["url"]


def test_missing_file_is_a_clean_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_request", FakeApi({}))
    assert cli.main(["upload", "/nope/missing.json"]) == 1
    assert "no such file" in capsys.readouterr().err


def test_incident_to_frames_orders_and_rebases(
    sample_incidents: dict[str, dict[str, Any]],
) -> None:
    incident = sample_incidents["obstacle"]
    frames = cli.incident_to_frames(incident)

    assert frames[0]["type"] == "hello"
    assert frames[0]["meta"]["task_name"] == "Deliver pallet to Loading Bay B"

    body = frames[1:]
    events = [f for f in body if f["type"] == "event"]
    samples = [f for f in body if f["type"] == "sample"]
    assert len(samples) > 100
    # Time-ordered absolute timestamps throughout.
    times = [f["t"] for f in body]
    assert times == sorted(times)
    # The replay stops at the FIRST terminal event (the server cuts
    # there; later frames would start a spurious second incident).
    assert body[-1]["type"] == "event"
    assert body[-1]["event_type"] == "task_timed_out"
    assert len(events) == len(incident["events"]) - 1
    assert all(f["type"] != "cut" for f in body)


def test_incident_to_frames_appends_cut_for_success_runs(
    sample_incidents: dict[str, dict[str, Any]],
) -> None:
    frames = cli.incident_to_frames(sample_incidents["baseline"])
    cut = frames[-1]
    assert cut["type"] == "cut"
    assert cut["id"] == "INC-2026-0721-BASE"
    assert cut["outcome"] == "success"
