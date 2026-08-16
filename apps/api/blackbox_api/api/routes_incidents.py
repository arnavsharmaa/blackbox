from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from blackbox_api.ai.explain import ai_available, generate_ai_explanation
from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.diff import DiffResponse, compute_diff
from blackbox_api.ingestion.base import IngestError
from blackbox_api.ingestion.service import ingest_incident
from blackbox_api.logging import log
from blackbox_api.reports.github_issue import build_github_issue
from blackbox_api.reports.report import build_report, report_markdown
from blackbox_api.schemas import (
    AnalysisResult,
    EventType,
    FailureCategory,
    Incident,
    IncidentDetail,
    IncidentEvent,
    IncidentListResponse,
    Outcome,
    Severity,
    TelemetrySeries,
)
from blackbox_api.storage.db import get_db
from blackbox_api.storage.repository import IncidentFilters, IncidentRepository

logger = logging.getLogger("blackbox.api")

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _get_incident_or_404(repo: IncidentRepository, incident_id: str) -> Incident:
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(
            status_code=404, detail=f"incident '{incident_id}' not found"
        )
    return incident


@router.get("", response_model=IncidentListResponse)
def list_incidents(
    db: Annotated[Session, Depends(get_db)],
    robot_id: str | None = None,
    severity: Severity | None = None,
    outcome: Outcome | None = None,
    failure_category: FailureCategory | None = None,
    start_after: datetime | None = None,
    start_before: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> IncidentListResponse:
    repo = IncidentRepository(db)
    items, total = repo.list_incidents(
        IncidentFilters(
            robot_id=robot_id,
            severity=severity,
            outcome=outcome,
            failure_category=failure_category,
            start_after=start_after,
            start_before=start_before,
        ),
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: str, db: Annotated[Session, Depends(get_db)]
) -> IncidentDetail:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    return IncidentDetail(incident=incident, analysis=repo.get_analysis(incident_id))


@router.get("/{incident_id}/events", response_model=list[IncidentEvent])
def get_events(
    incident_id: str,
    db: Annotated[Session, Depends(get_db)],
    event_type: EventType | None = None,
    severity: Severity | None = None,
) -> list[IncidentEvent]:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    events = incident.events
    if event_type is not None:
        events = [e for e in events if e.event_type == event_type]
    if severity is not None:
        events = [e for e in events if e.severity == severity]
    return events


@router.get("/{incident_id}/telemetry", response_model=list[TelemetrySeries])
def get_telemetry(
    incident_id: str,
    db: Annotated[Session, Depends(get_db)],
    channel: str | None = None,
) -> list[TelemetrySeries]:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    series = incident.telemetry
    if channel is not None:
        series = [s for s in series if s.channel.value == channel]
    return series


@router.get("/{incident_id}/analysis", response_model=AnalysisResult)
def get_analysis(
    incident_id: str,
    db: Annotated[Session, Depends(get_db)],
    ai: bool = Query(
        default=False,
        description="Attach an AI-generated summary if an API key is configured. "
        "Never affects the deterministic diagnosis.",
    ),
) -> AnalysisResult:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    analysis = repo.get_analysis(incident_id)
    if analysis is None:
        analysis = analyze_incident(incident)
        repo.save_analysis(analysis)
        db.commit()
    if ai and analysis.ai_explanation is None and ai_available():
        explanation = generate_ai_explanation(incident, analysis)
        if explanation is not None:
            analysis = analysis.model_copy(update={"ai_explanation": explanation})
            repo.save_analysis(analysis)
            db.commit()
    return analysis


@router.get("/{incident_id}/diff/{baseline_id}", response_model=DiffResponse)
def diff_incidents(
    incident_id: str, baseline_id: str, db: Annotated[Session, Depends(get_db)]
) -> DiffResponse:
    """Compare an incident against a baseline run of the same task."""
    if incident_id == baseline_id:
        raise HTTPException(
            status_code=400,
            detail="cannot diff an incident against itself",
        )
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    baseline = _get_incident_or_404(repo, baseline_id)
    return compute_diff(incident, baseline)


@router.delete("/{incident_id}", status_code=204)
def delete_incident(
    incident_id: str, db: Annotated[Session, Depends(get_db)]
) -> None:
    repo = IncidentRepository(db)
    if not repo.delete_incident(incident_id):
        raise HTTPException(
            status_code=404, detail=f"incident '{incident_id}' not found"
        )
    db.commit()
    log(logger, logging.INFO, "incident deleted", incident_id=incident_id)


class ReanalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    analysis: AnalysisResult


@router.post("/{incident_id}/reanalyze", response_model=ReanalyzeResponse)
def reanalyze(
    incident_id: str, db: Annotated[Session, Depends(get_db)]
) -> ReanalyzeResponse:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    analysis = analyze_incident(incident)
    repo.save_analysis(analysis)
    db.commit()
    log(logger, logging.INFO, "incident reanalyzed", incident_id=incident_id)
    return ReanalyzeResponse(incident_id=incident_id, analysis=analysis)


@router.get("/{incident_id}/report")
def get_report(
    incident_id: str,
    db: Annotated[Session, Depends(get_db)],
    format: str = Query(default="json", pattern="^(json|markdown)$"),
) -> Any:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    analysis = repo.get_analysis(incident_id)
    if format == "markdown":
        return {"markdown": report_markdown(incident, analysis)}
    report = build_report(incident, analysis)
    report["markdown"] = report_markdown(incident, analysis)
    return report


@router.get("/{incident_id}/github-issue")
def get_github_issue(
    incident_id: str,
    db: Annotated[Session, Depends(get_db)],
    repo_name: str | None = Query(
        default=None,
        alias="repo",
        description="Optional 'owner/repo' used to build a prefilled issue URL",
    ),
) -> Any:
    repo = IncidentRepository(db)
    incident = _get_incident_or_404(repo, incident_id)
    analysis = repo.get_analysis(incident_id)
    return build_github_issue(incident, analysis, repo=repo_name)


class UploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    event_count: int
    telemetry_channels: int
    failure_category: FailureCategory
    confidence: float


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_incident(
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile,
    metadata: Annotated[
        str | None,
        Form(
            description="Incident metadata JSON — required for CSV event uploads, "
            "optional overrides for JSON uploads"
        ),
    ] = None,
) -> UploadResponse:
    meta_dict: dict[str, Any] | None = None
    if metadata:
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "metadata form field is not valid JSON",
                    "errors": [{"field": "metadata", "error": exc.msg}],
                },
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "metadata must be a JSON object",
                    "errors": [{"field": "metadata", "error": "expected object"}],
                },
            )
        meta_dict = parsed

    raw = await file.read()
    try:
        incident, analysis = ingest_incident(
            db, raw, file.filename or "upload.json", metadata=meta_dict
        )
        db.commit()
    except IngestError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={"message": exc.message, "errors": exc.details},
        ) from exc
    return UploadResponse(
        incident_id=incident.id,
        event_count=len(incident.events),
        telemetry_channels=len(incident.telemetry),
        failure_category=analysis.failure_category,
        confidence=analysis.confidence,
    )
