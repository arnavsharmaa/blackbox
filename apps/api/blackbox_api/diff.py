"""Compare a failed incident against a known-good baseline run.

Aligns telemetry channel-by-channel on the runs' own clocks (t seconds
from each run's start), computes per-channel deltas, and finds the first
sustained divergence — the moment the failing run stopped looking like
the good one. Deterministic, like the analysis engine: same inputs,
same diff.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from typing import cast

from pydantic import BaseModel, ConfigDict

from blackbox_api.schemas import (
    STRING_CHANNELS,
    EventType,
    Incident,
    Outcome,
    TelemetryChannel,
)

#: Fraction of the baseline channel's value range a delta must exceed
#: before it counts toward a divergence.
DIVERGENCE_RANGE_FRACTION = 0.15
#: Consecutive incident samples beyond the threshold required for a
#: divergence to count as sustained (filters one-sample noise).
SUSTAIN_SAMPLES = 3
#: Floor for the delta threshold, for channels with a flat baseline.
MIN_DELTA_THRESHOLD = 0.05


class RunRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    robot_id: str
    task_name: str
    outcome: Outcome
    duration_s: float


class ChannelDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: TelemetryChannel
    #: Delta threshold used for this channel; None for string channels,
    #: which diverge on any value mismatch instead.
    delta_threshold: float | None
    max_abs_delta: float | None
    max_abs_delta_t: float | None
    first_divergence_t: float | None


class EventTypeDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    incident_count: int
    baseline_count: int


class DiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident: RunRef
    baseline: RunRef
    #: Shared channels, diverging ones first (by divergence time).
    channels: list[ChannelDiff]
    first_divergence_t: float | None
    first_divergence_channel: TelemetryChannel | None
    events: list[EventTypeDelta]
    event_types_only_in_incident: list[EventType]


def _run_ref(incident: Incident) -> RunRef:
    return RunRef(
        id=incident.id,
        robot_id=incident.robot_id,
        task_name=incident.task_name,
        outcome=incident.outcome,
        duration_s=incident.duration_s,
    )


class _Held:
    """Sample-and-hold lookup over one telemetry series."""

    def __init__(self, samples: list[tuple[float, float | str]]) -> None:
        self._ts = [t for t, _ in samples]
        self._values = [v for _, v in samples]

    def at(self, t: float) -> float | str:
        idx = bisect_right(self._ts, t) - 1
        return self._values[max(idx, 0)]


def _numeric_channel_diff(
    channel: TelemetryChannel,
    incident_samples: list[tuple[float, float]],
    baseline_samples: list[tuple[float, float]],
    overlap_end: float,
) -> ChannelDiff:
    baseline_values = [v for _, v in baseline_samples]
    value_range = max(baseline_values) - min(baseline_values)
    threshold = max(
        DIVERGENCE_RANGE_FRACTION * value_range, MIN_DELTA_THRESHOLD
    )
    held = _Held(cast("list[tuple[float, float | str]]", baseline_samples))

    max_delta = 0.0
    max_delta_t: float | None = None
    first_divergence: float | None = None
    streak_start: float | None = None
    streak = 0
    for t, value in incident_samples:
        if t > overlap_end:
            break
        delta = abs(value - cast(float, held.at(t)))
        if max_delta_t is None or delta > max_delta:
            max_delta, max_delta_t = delta, t
        if delta > threshold:
            if streak == 0:
                streak_start = t
            streak += 1
            if streak >= SUSTAIN_SAMPLES and first_divergence is None:
                first_divergence = streak_start
        else:
            streak = 0
    return ChannelDiff(
        channel=channel,
        delta_threshold=round(threshold, 6),
        max_abs_delta=round(max_delta, 6),
        max_abs_delta_t=max_delta_t,
        first_divergence_t=first_divergence,
    )


def _string_channel_diff(
    channel: TelemetryChannel,
    incident_samples: list[tuple[float, float | str]],
    baseline_samples: list[tuple[float, float | str]],
    overlap_end: float,
) -> ChannelDiff:
    """String channels (e.g. planner_state) diverge on any mismatch."""
    inc_held = _Held(incident_samples)
    base_held = _Held(baseline_samples)
    checkpoints = sorted(
        {t for t, _ in incident_samples} | {t for t, _ in baseline_samples}
    )
    first_divergence = next(
        (
            t
            for t in checkpoints
            if t <= overlap_end and inc_held.at(t) != base_held.at(t)
        ),
        None,
    )
    return ChannelDiff(
        channel=channel,
        delta_threshold=None,
        max_abs_delta=None,
        max_abs_delta_t=None,
        first_divergence_t=first_divergence,
    )


def compute_diff(incident: Incident, baseline: Incident) -> DiffResponse:
    overlap_end = min(incident.duration_s, baseline.duration_s)
    incident_series = {s.channel: s.samples for s in incident.telemetry}
    baseline_series = {s.channel: s.samples for s in baseline.telemetry}

    channel_order = list(TelemetryChannel)
    channels: list[ChannelDiff] = []
    for channel in channel_order:
        inc = incident_series.get(channel)
        base = baseline_series.get(channel)
        if not inc or not base:
            continue
        inc_pairs = [(s.t, s.value) for s in inc]
        base_pairs = [(s.t, s.value) for s in base]
        if channel in STRING_CHANNELS:
            channels.append(
                _string_channel_diff(channel, inc_pairs, base_pairs, overlap_end)
            )
        else:
            channels.append(_numeric_channel_diff(
                channel,
                cast("list[tuple[float, float]]", inc_pairs),
                cast("list[tuple[float, float]]", base_pairs),
                overlap_end,
            ))

    channels.sort(
        key=lambda c: (
            c.first_divergence_t is None,
            c.first_divergence_t if c.first_divergence_t is not None else 0.0,
            channel_order.index(c.channel),
        )
    )
    first = next(
        (c for c in channels if c.first_divergence_t is not None), None
    )

    incident_counts = Counter(e.event_type for e in incident.events)
    baseline_counts = Counter(e.event_type for e in baseline.events)
    events = [
        EventTypeDelta(
            event_type=event_type,
            incident_count=incident_counts.get(event_type, 0),
            baseline_count=baseline_counts.get(event_type, 0),
        )
        for event_type in EventType
        if event_type in incident_counts or event_type in baseline_counts
    ]

    return DiffResponse(
        incident=_run_ref(incident),
        baseline=_run_ref(baseline),
        channels=channels,
        first_divergence_t=first.first_divergence_t if first else None,
        first_divergence_channel=first.channel if first else None,
        events=events,
        event_types_only_in_incident=[
            e for e in EventType
            if e in incident_counts and e not in baseline_counts
        ],
    )
