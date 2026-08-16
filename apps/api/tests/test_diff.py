from __future__ import annotations

from fastapi.testclient import TestClient

from blackbox_api.diff import compute_diff
from blackbox_api.schemas import Incident, TelemetryChannel

PRIMARY = "INC-2026-0728-001"
BASELINE = "INC-2026-0721-BASE"


def test_diff_finds_divergence_at_the_blockage(
    parsed_incidents: dict[str, Incident],
) -> None:
    diff = compute_diff(
        parsed_incidents["obstacle"], parsed_incidents["baseline"]
    )

    assert diff.incident.id == PRIMARY
    assert diff.baseline.id == BASELINE
    assert diff.baseline.outcome.value == "success"

    # The runs share the corridor route for the first ~26 s, then the
    # failed run stops at the pallet: divergence in the blockage window,
    # well before the t=90 timeout.
    assert diff.first_divergence_t is not None
    assert 20.0 <= diff.first_divergence_t <= 45.0
    assert diff.first_divergence_channel is not None

    by_channel = {c.channel: c for c in diff.channels}
    # The blocked robot's obstacle clearance collapses to 0.52 m while the
    # baseline stays near max range.
    obstacle = by_channel[TelemetryChannel.OBSTACLE_DISTANCE]
    assert obstacle.first_divergence_t is not None
    assert obstacle.max_abs_delta is not None
    assert obstacle.max_abs_delta > 3.0
    # The failed run never closes on the goal.
    assert by_channel[TelemetryChannel.GOAL_DISTANCE].first_divergence_t is not None
    # Localization stayed healthy in both runs — no divergence there.
    conf = by_channel[TelemetryChannel.LOCALIZATION_CONFIDENCE]
    assert conf.first_divergence_t is None

    # planner_state is compared as a string channel: the failure enters
    # "avoiding" while the baseline is still "executing".
    planner = by_channel[TelemetryChannel.PLANNER_STATE]
    assert planner.delta_threshold is None
    assert planner.first_divergence_t == 30.0

    # Diverging channels come first, ordered by divergence time.
    divergence_times = [
        c.first_divergence_t
        for c in diff.channels
        if c.first_divergence_t is not None
    ]
    assert divergence_times == sorted(divergence_times)
    assert diff.channels[0].first_divergence_t == diff.first_divergence_t


def test_diff_event_comparison(
    parsed_incidents: dict[str, Incident],
) -> None:
    diff = compute_diff(
        parsed_incidents["obstacle"], parsed_incidents["baseline"]
    )
    by_type = {e.event_type.value: e for e in diff.events}
    # Recoveries and failures only exist in the failed run.
    assert by_type["recovery_started"].incident_count == 3
    assert by_type["recovery_started"].baseline_count == 0
    assert by_type["task_failed"].incident_count == 1
    only = {e.value for e in diff.event_types_only_in_incident}
    assert {"recovery_started", "task_timed_out", "task_failed"} <= only
    # Both runs start their task.
    assert by_type["task_started"].baseline_count == 1


def test_diff_is_deterministic(
    parsed_incidents: dict[str, Incident],
) -> None:
    a = compute_diff(parsed_incidents["obstacle"], parsed_incidents["baseline"])
    b = compute_diff(parsed_incidents["obstacle"], parsed_incidents["baseline"])
    assert a.model_dump() == b.model_dump()


def test_diff_identical_runs_have_no_divergence(
    parsed_incidents: dict[str, Incident],
) -> None:
    baseline = parsed_incidents["baseline"]
    other = baseline.model_copy(update={"id": "INC-COPY"})
    diff = compute_diff(other, baseline)
    assert diff.first_divergence_t is None
    assert diff.first_divergence_channel is None
    assert all(c.first_divergence_t is None for c in diff.channels)
    assert diff.event_types_only_in_incident == []


def test_diff_endpoint(seeded_client: TestClient) -> None:
    response = seeded_client.get(f"/api/incidents/{PRIMARY}/diff/{BASELINE}")
    assert response.status_code == 200
    body = response.json()
    assert body["incident"]["id"] == PRIMARY
    assert body["baseline"]["id"] == BASELINE
    assert body["first_divergence_t"] is not None
    assert len(body["channels"]) >= 8


def test_diff_endpoint_errors(seeded_client: TestClient) -> None:
    assert (
        seeded_client.get(f"/api/incidents/{PRIMARY}/diff/NOPE").status_code
        == 404
    )
    assert (
        seeded_client.get(f"/api/incidents/NOPE/diff/{BASELINE}").status_code
        == 404
    )
    assert (
        seeded_client.get(
            f"/api/incidents/{PRIMARY}/diff/{PRIMARY}"
        ).status_code
        == 400
    )
