"""Canonical BlackBox incident schema.

This module is the single source of truth for the incident data model. The
TypeScript mirror lives in packages/schemas/src/incident.ts and must be kept
in sync (verified by tests/test_schema_sync.py against the exported JSON
schema in packages/schemas/incident.schema.json).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Outcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"


class FailureCategory(StrEnum):
    PERSISTENT_OBSTACLE = "persistent_obstacle"
    LOCALIZATION_FAILURE = "localization_failure"
    CONTROLLER_OSCILLATION = "controller_oscillation"
    SENSOR_DROPOUT = "sensor_dropout"
    UNKNOWN = "unknown"


class Subsystem(StrEnum):
    TASK_MANAGER = "task_manager"
    NAVIGATION = "navigation"
    PLANNER = "planner"
    CONTROLLER = "controller"
    LOCALIZATION = "localization"
    PERCEPTION = "perception"
    SYSTEM = "system"


class EventType(StrEnum):
    TASK_STARTED = "task_started"
    NAV_GOAL_ISSUED = "nav_goal_issued"
    POSE_UPDATED = "pose_updated"
    VELOCITY_COMMAND = "velocity_command"
    PLANNER_STATE_CHANGED = "planner_state_changed"
    OBSTACLE_DISTANCE_UPDATED = "obstacle_distance_updated"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    WARNING_RAISED = "warning_raised"
    ERROR_RAISED = "error_raised"
    TASK_TIMED_OUT = "task_timed_out"
    TASK_FAILED = "task_failed"


class TelemetryChannel(StrEnum):
    POS_X = "pos_x"
    POS_Y = "pos_y"
    HEADING = "heading"
    LINEAR_VELOCITY = "linear_velocity"
    ANGULAR_VELOCITY = "angular_velocity"
    OBSTACLE_DISTANCE = "obstacle_distance"
    GOAL_DISTANCE = "goal_distance"
    LOCALIZATION_CONFIDENCE = "localization_confidence"
    PLANNER_STATE = "planner_state"
    RECOVERY_COUNT = "recovery_count"
    BATTERY_PCT = "battery_pct"


# Channels whose samples carry string values instead of numbers.
STRING_CHANNELS = {TelemetryChannel.PLANNER_STATE}


class IncidentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    event_type: EventType
    subsystem: Subsystem
    severity: Severity = Severity.INFO
    message: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    evidence_tags: list[str] = Field(default_factory=list)


class TelemetrySample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: float = Field(ge=0, description="Seconds since incident start_time")
    value: float | str


class TelemetrySeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: TelemetryChannel
    unit: str = ""
    samples: list[TelemetrySample]

    @model_validator(mode="after")
    def _check_sample_types(self) -> TelemetrySeries:
        wants_str = self.channel in STRING_CHANNELS
        for s in self.samples:
            if wants_str != isinstance(s.value, str):
                kind = "string" if wants_str else "numeric"
                raise ValueError(
                    f"channel '{self.channel.value}' requires {kind} sample "
                    f"values (offending sample at t={s.t})"
                )
        prev = -1.0
        for s in self.samples:
            if s.t < prev:
                raise ValueError(
                    f"channel '{self.channel.value}' samples must be ordered "
                    f"by t (t={s.t} follows t={prev})"
                )
            prev = s.t
        return self


class Incident(BaseModel):
    """A complete incident as ingested into BlackBox."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._:-]+$")
    robot_id: str = Field(min_length=1)
    robot_model: str = Field(min_length=1)
    facility: str = Field(min_length=1)
    task_name: str = Field(min_length=1)
    task_goal: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    outcome: Outcome
    severity: Severity
    software_version: str = Field(min_length=1)
    map_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    events: list[IncidentEvent] = Field(min_length=1)
    telemetry: list[TelemetrySeries] = Field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return (self.end_time - self.start_time).total_seconds()

    @field_validator("events")
    @classmethod
    def _sort_events(cls, events: list[IncidentEvent]) -> list[IncidentEvent]:
        # Adapters may deliver events out of order; canonical form is sorted.
        return sorted(events, key=lambda e: e.timestamp)

    @model_validator(mode="after")
    def _check_times(self) -> Incident:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        first = self.events[0].timestamp
        last = self.events[-1].timestamp
        if first < self.start_time or last > self.end_time:
            raise ValueError(
                "all event timestamps must fall within [start_time, end_time]"
            )
        duration = self.duration_s
        for series in self.telemetry:
            if series.samples and series.samples[-1].t > duration + 1e-6:
                raise ValueError(
                    f"telemetry channel '{series.channel.value}' extends past "
                    f"incident duration ({series.samples[-1].t:.2f}s > "
                    f"{duration:.2f}s)"
                )
        seen: set[TelemetryChannel] = set()
        for series in self.telemetry:
            if series.channel in seen:
                raise ValueError(
                    f"duplicate telemetry channel '{series.channel.value}'"
                )
            seen.add(series.channel)
        return self


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    detail: str = ""
    t: float = Field(ge=0, description="Anchor time (s since incident start)")
    t_end: float | None = None
    channel: TelemetryChannel | None = None
    tags: list[str] = Field(default_factory=list)


class AlternativeCause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    score: float = Field(ge=0, le=1)
    reason: str


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    engine_version: str
    failure_category: FailureCategory
    confidence: float = Field(ge=0, le=1)
    explanation: str
    recommended_actions: list[str]
    evidence: list[EvidenceItem]
    alternative_causes: list[AlternativeCause]
    rules_triggered: list[str]
    analyzed_at: datetime
    ai_explanation: str | None = Field(
        default=None,
        description="Optional AI-generated summary of the deterministic "
        "analysis. Never used to determine the root cause.",
    )


class FeedbackVerdict(StrEnum):
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"


class DiagnosisFeedback(BaseModel):
    """An engineer's verdict on a stored diagnosis.

    The raw material for confidence calibration: fleet analytics computes
    per-category precision from these, so "95% confidence" can be checked
    against how often engineers actually agreed.
    """

    model_config = ConfigDict(extra="forbid")

    incident_id: str
    verdict: FeedbackVerdict
    diagnosed_category: FailureCategory = Field(
        description="What the engine said at the time feedback was given"
    )
    actual_category: FailureCategory | None = Field(
        default=None,
        description="The human-determined category; required when corrected",
    )
    note: str = ""
    created_at: datetime

    @model_validator(mode="after")
    def _check_actual_category(self) -> DiagnosisFeedback:
        if (
            self.verdict is FeedbackVerdict.CORRECTED
            and self.actual_category is None
        ):
            raise ValueError("corrected feedback requires actual_category")
        if (
            self.verdict is FeedbackVerdict.CONFIRMED
            and self.actual_category is not None
        ):
            raise ValueError("confirmed feedback must not set actual_category")
        return self


class IncidentSummary(BaseModel):
    """Compact incident representation for list views."""

    model_config = ConfigDict(extra="forbid")

    id: str
    robot_id: str
    robot_model: str
    facility: str
    task_name: str
    start_time: datetime
    end_time: datetime
    duration_s: float
    outcome: Outcome
    severity: Severity
    software_version: str
    summary: str
    event_count: int
    recovery_attempts: int
    failure_category: FailureCategory | None = None
    confidence: float | None = None


class IncidentDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident: Incident
    analysis: AnalysisResult | None = None
    feedback: DiagnosisFeedback | None = None


class IncidentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[IncidentSummary]
    total: int
    limit: int
    offset: int
