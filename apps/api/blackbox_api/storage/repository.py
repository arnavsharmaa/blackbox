from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from blackbox_api.schemas import (
    AnalysisResult,
    DiagnosisFeedback,
    FailureCategory,
    Incident,
    IncidentEvent,
    IncidentNote,
    IncidentSummary,
    Outcome,
    Severity,
    TelemetrySample,
    TelemetrySeries,
    TriageState,
)
from blackbox_api.storage.models import (
    AnalysisRow,
    EventRow,
    FeedbackRow,
    IncidentRow,
    NoteRow,
    TelemetrySeriesRow,
)


class IncidentFilters:
    def __init__(
        self,
        robot_id: str | None = None,
        severity: Severity | None = None,
        outcome: Outcome | None = None,
        failure_category: FailureCategory | None = None,
        start_after: datetime | None = None,
        start_before: datetime | None = None,
        q: str | None = None,
        facility: str | None = None,
        task_name: str | None = None,
        triage: TriageState | None = None,
    ) -> None:
        self.robot_id = robot_id
        self.severity = severity
        self.outcome = outcome
        self.failure_category = failure_category
        self.start_after = start_after
        self.start_before = start_before
        self.q = q
        self.facility = facility
        self.task_name = task_name
        self.triage = triage


class IncidentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- writes ---

    def upsert_incident(self, incident: Incident) -> None:
        existing = self.session.get(IncidentRow, incident.id)
        if existing is not None:
            self.session.delete(existing)
            self.session.flush()

        row = IncidentRow(
            id=incident.id,
            schema_version=incident.schema_version,
            robot_id=incident.robot_id,
            robot_model=incident.robot_model,
            facility=incident.facility,
            task_name=incident.task_name,
            task_goal=incident.task_goal,
            start_time=incident.start_time,
            end_time=incident.end_time,
            duration_s=incident.duration_s,
            outcome=incident.outcome.value,
            severity=incident.severity.value,
            software_version=incident.software_version,
            map_version=incident.map_version,
            environment=incident.environment,
            summary=incident.summary,
            created_at=datetime.now(UTC),
        )
        for idx, ev in enumerate(incident.events):
            row.events.append(
                EventRow(
                    idx=idx,
                    timestamp=ev.timestamp,
                    event_type=ev.event_type.value,
                    subsystem=ev.subsystem.value,
                    severity=ev.severity.value,
                    message=ev.message,
                    payload_json=json.dumps(ev.payload),
                    correlation_id=ev.correlation_id,
                    evidence_tags_json=json.dumps(ev.evidence_tags),
                )
            )
        for series in incident.telemetry:
            row.telemetry.append(
                TelemetrySeriesRow(
                    channel=series.channel.value,
                    unit=series.unit,
                    samples_json=json.dumps(
                        [[s.t, s.value] for s in series.samples]
                    ),
                )
            )
        self.session.add(row)

    def save_analysis(self, result: AnalysisResult) -> None:
        existing = self.session.get(AnalysisRow, result.incident_id)
        if existing is not None:
            self.session.delete(existing)
            self.session.flush()
        self.session.add(
            AnalysisRow(
                incident_id=result.incident_id,
                engine_version=result.engine_version,
                result_json=result.model_dump_json(),
                analyzed_at=result.analyzed_at,
            )
        )

    def save_feedback(self, feedback: DiagnosisFeedback) -> None:
        existing = self.session.get(FeedbackRow, feedback.incident_id)
        if existing is not None:
            self.session.delete(existing)
            self.session.flush()
        self.session.add(
            FeedbackRow(
                incident_id=feedback.incident_id,
                verdict=feedback.verdict.value,
                diagnosed_category=feedback.diagnosed_category.value,
                actual_category=(
                    feedback.actual_category.value
                    if feedback.actual_category
                    else None
                ),
                note=feedback.note,
                created_at=feedback.created_at,
            )
        )

    def delete_incidents_before(
        self, cutoff: datetime, facility: str | None = None
    ) -> list[str]:
        """Delete incidents started before the cutoff; returns their ids.

        ORM-level deletes so events, telemetry, analyses, and feedback
        cascade regardless of database FK enforcement. A facility limits
        the prune to that tenant's incidents.
        """
        stmt = select(IncidentRow).where(IncidentRow.start_time < cutoff)
        if facility is not None:
            stmt = stmt.where(IncidentRow.facility == facility)
        rows = self.session.scalars(stmt).all()
        for row in rows:
            self.session.delete(row)
        return [row.id for row in rows]

    def get_triage(self, incident_id: str) -> TriageState:
        row = self.session.get(IncidentRow, incident_id)
        return (
            TriageState(row.triage_state)
            if row is not None
            else TriageState.OPEN
        )

    def resolution_hours(
        self,
        facility: str | None = None,
        start_after: datetime | None = None,
        start_before: datetime | None = None,
    ) -> list[float]:
        """Hours from ingest to resolution, one per resolved incident.

        Incidents resolved before transitions were timestamped
        (pre-0005 databases) have no duration and are skipped.
        """
        stmt = select(
            IncidentRow.created_at, IncidentRow.triage_updated_at
        ).where(
            IncidentRow.triage_state == TriageState.RESOLVED.value,
            IncidentRow.triage_updated_at.is_not(None),
        )
        if facility:
            stmt = stmt.where(IncidentRow.facility == facility)
        if start_after:
            stmt = stmt.where(IncidentRow.start_time >= start_after)
        if start_before:
            stmt = stmt.where(IncidentRow.start_time <= start_before)
        hours: list[float] = []
        for created, resolved in self.session.execute(stmt):
            if resolved is None:  # excluded in SQL; narrows the type
                continue
            delta = (_utc(resolved) - _utc(created)).total_seconds() / 3600
            hours.append(max(0.0, round(delta, 2)))
        return hours

    def get_created_at(self, incident_id: str) -> datetime | None:
        """When the incident was ingested (None for a missing id)."""
        row = self.session.get(IncidentRow, incident_id)
        return _utc(row.created_at) if row is not None else None

    def get_triage_info(
        self, incident_id: str
    ) -> tuple[TriageState, datetime | None]:
        """Current triage state and when it last changed (None if never)."""
        row = self.session.get(IncidentRow, incident_id)
        if row is None:
            return TriageState.OPEN, None
        updated = (
            _utc(row.triage_updated_at) if row.triage_updated_at else None
        )
        return TriageState(row.triage_state), updated

    def set_triage(
        self, incident_id: str, state: TriageState
    ) -> datetime | None:
        """Set the state; returns the transition timestamp (None = 404)."""
        row = self.session.get(IncidentRow, incident_id)
        if row is None:
            return None
        row.triage_state = state.value
        row.triage_updated_at = datetime.now(UTC)
        return row.triage_updated_at

    def delete_incident(self, incident_id: str) -> bool:
        row = self.session.get(IncidentRow, incident_id)
        if row is None:
            return False
        self.session.delete(row)
        return True

    # --- reads ---

    def get_incident(self, incident_id: str) -> Incident | None:
        row = self.session.get(
            IncidentRow,
            incident_id,
            options=[
                selectinload(IncidentRow.events),
                selectinload(IncidentRow.telemetry),
            ],
        )
        if row is None:
            return None
        return self._row_to_incident(row)

    def get_analysis(self, incident_id: str) -> AnalysisResult | None:
        row = self.session.get(AnalysisRow, incident_id)
        if row is None:
            return None
        return AnalysisResult.model_validate_json(row.result_json)

    def add_note(
        self, incident_id: str, text: str, author: str = ""
    ) -> IncidentNote:
        row = NoteRow(
            incident_id=incident_id,
            text=text,
            author=author,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.flush()  # assign the autoincrement id
        return self._row_to_note(row)

    def delete_note(self, incident_id: str, note_id: int) -> bool:
        row = self.session.get(NoteRow, note_id)
        if row is None or row.incident_id != incident_id:
            return False
        self.session.delete(row)
        return True

    def list_notes(self, incident_id: str) -> list[IncidentNote]:
        rows = self.session.scalars(
            select(NoteRow)
            .where(NoteRow.incident_id == incident_id)
            .order_by(NoteRow.id)
        ).all()
        return [self._row_to_note(row) for row in rows]

    def _row_to_note(self, row: NoteRow) -> IncidentNote:
        return IncidentNote(
            id=row.id,
            incident_id=row.incident_id,
            text=row.text,
            author=row.author,
            created_at=_utc(row.created_at),
        )

    def get_feedback(self, incident_id: str) -> DiagnosisFeedback | None:
        row = self.session.get(FeedbackRow, incident_id)
        if row is None:
            return None
        return self._row_to_feedback(row)

    def list_feedback(
        self, facility: str | None = None
    ) -> list[DiagnosisFeedback]:
        stmt = select(FeedbackRow)
        if facility is not None:
            stmt = stmt.join(
                IncidentRow, FeedbackRow.incident_id == IncidentRow.id
            ).where(IncidentRow.facility == facility)
        rows = self.session.scalars(stmt).all()
        return [self._row_to_feedback(row) for row in rows]

    def _row_to_feedback(self, row: FeedbackRow) -> DiagnosisFeedback:
        return DiagnosisFeedback(
            incident_id=row.incident_id,
            verdict=row.verdict,  # type: ignore[arg-type]
            diagnosed_category=row.diagnosed_category,  # type: ignore[arg-type]
            actual_category=row.actual_category,  # type: ignore[arg-type]
            note=row.note,
            created_at=_utc(row.created_at),
        )

    def list_incidents(
        self, filters: IncidentFilters, limit: int = 50, offset: int = 0
    ) -> tuple[list[IncidentSummary], int]:
        stmt = select(IncidentRow).options(selectinload(IncidentRow.analysis))
        count_stmt = select(func.count(IncidentRow.id))

        conditions = []
        if filters.robot_id:
            conditions.append(IncidentRow.robot_id == filters.robot_id)
        if filters.facility:
            conditions.append(IncidentRow.facility == filters.facility)
        if filters.task_name:
            conditions.append(IncidentRow.task_name == filters.task_name)
        if filters.triage:
            conditions.append(
                IncidentRow.triage_state == filters.triage.value
            )
        if filters.severity:
            conditions.append(IncidentRow.severity == filters.severity.value)
        if filters.outcome:
            conditions.append(IncidentRow.outcome == filters.outcome.value)
        if filters.start_after:
            conditions.append(IncidentRow.start_time >= filters.start_after)
        if filters.start_before:
            conditions.append(IncidentRow.start_time <= filters.start_before)
        if filters.q:
            # Case-insensitive substring search across the fields an
            # engineer would paste or remember (ilike works on both
            # SQLite and Postgres).
            needle = f"%{filters.q.strip()}%"
            conditions.append(
                IncidentRow.id.ilike(needle)
                | IncidentRow.task_name.ilike(needle)
                | IncidentRow.summary.ilike(needle)
                | IncidentRow.robot_id.ilike(needle)
            )
        if filters.failure_category:
            cat_ids = select(AnalysisRow.incident_id).where(
                AnalysisRow.result_json.like(
                    f'%"failure_category":"{filters.failure_category.value}"%'
                )
            )
            conditions.append(IncidentRow.id.in_(cat_ids))
        for cond in conditions:
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total = self.session.scalar(count_stmt) or 0
        rows = (
            self.session.scalars(
                stmt.order_by(IncidentRow.start_time.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()

        summaries: list[IncidentSummary] = []
        for row in rows:
            event_count = self.session.scalar(
                select(func.count(EventRow.id)).where(
                    EventRow.incident_id == row.id
                )
            )
            recovery_attempts = self.session.scalar(
                select(func.count(EventRow.id)).where(
                    EventRow.incident_id == row.id,
                    EventRow.event_type == "recovery_started",
                )
            )
            analysis = (
                AnalysisResult.model_validate_json(row.analysis.result_json)
                if row.analysis
                else None
            )
            summaries.append(
                IncidentSummary(
                    id=row.id,
                    robot_id=row.robot_id,
                    robot_model=row.robot_model,
                    facility=row.facility,
                    task_name=row.task_name,
                    start_time=_utc(row.start_time),
                    end_time=_utc(row.end_time),
                    duration_s=row.duration_s,
                    outcome=Outcome(row.outcome),
                    severity=Severity(row.severity),
                    software_version=row.software_version,
                    summary=row.summary,
                    event_count=event_count or 0,
                    recovery_attempts=recovery_attempts or 0,
                    failure_category=analysis.failure_category if analysis else None,
                    confidence=analysis.confidence if analysis else None,
                    triage_state=TriageState(row.triage_state),
                )
            )
        return summaries, total

    def list_all_ids(self) -> list[str]:
        return list(self.session.scalars(select(IncidentRow.id)).all())

    def _row_to_incident(self, row: IncidentRow) -> Incident:
        events = [
            IncidentEvent(
                timestamp=_utc(ev.timestamp),
                event_type=ev.event_type,  # type: ignore[arg-type]
                subsystem=ev.subsystem,  # type: ignore[arg-type]
                severity=ev.severity,  # type: ignore[arg-type]
                message=ev.message,
                payload=json.loads(ev.payload_json),
                correlation_id=ev.correlation_id,
                evidence_tags=json.loads(ev.evidence_tags_json),
            )
            for ev in row.events
        ]
        telemetry = [
            TelemetrySeries(
                channel=series.channel,  # type: ignore[arg-type]
                unit=series.unit,
                samples=[
                    TelemetrySample(t=t, value=value)
                    for t, value in json.loads(series.samples_json)
                ],
            )
            for series in row.telemetry
        ]
        return Incident(
            schema_version=row.schema_version,
            id=row.id,
            robot_id=row.robot_id,
            robot_model=row.robot_model,
            facility=row.facility,
            task_name=row.task_name,
            task_goal=row.task_goal,
            start_time=_utc(row.start_time),
            end_time=_utc(row.end_time),
            outcome=row.outcome,  # type: ignore[arg-type]
            severity=row.severity,  # type: ignore[arg-type]
            software_version=row.software_version,
            map_version=row.map_version,
            environment=row.environment,
            summary=row.summary,
            events=events,
            telemetry=telemetry,
        )


def _utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo; restore UTC on the way out."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
