from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.config import get_settings
from blackbox_api.ingestion.base import IncidentAdapter, IngestError
from blackbox_api.ingestion.csv_adapter import CsvIncidentAdapter
from blackbox_api.ingestion.json_adapter import JsonIncidentAdapter
from blackbox_api.ingestion.rosbag2_adapter import Rosbag2Adapter
from blackbox_api.logging import log
from blackbox_api.schemas import AnalysisResult, Incident
from blackbox_api.storage.repository import IncidentRepository

logger = logging.getLogger("blackbox.ingestion")

ADAPTERS: tuple[IncidentAdapter, ...] = (
    JsonIncidentAdapter(),
    CsvIncidentAdapter(),
    Rosbag2Adapter(),
)



def adapter_for_filename(filename: str) -> IncidentAdapter:
    ext = Path(filename).suffix.lower()
    for adapter in ADAPTERS:
        if ext in adapter.extensions:
            return adapter
    supported = ", ".join(e for a in ADAPTERS for e in a.extensions)
    raise IngestError(
        f"unsupported file type '{ext or filename}'; supported: {supported}"
    )


def ingest_incident(
    session: Session,
    raw: bytes,
    filename: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[Incident, AnalysisResult]:
    """Parse, validate, persist and analyze an incident payload."""
    max_mb = get_settings().max_upload_mb
    if len(raw) > max_mb * 1024 * 1024:
        raise IngestError(f"upload exceeds the {max_mb} MB limit")
    if not raw.strip():
        raise IngestError("uploaded file is empty")

    adapter = adapter_for_filename(filename)
    incident = adapter.parse(raw, metadata=metadata)
    analysis = analyze_incident(incident)

    repo = IncidentRepository(session)
    repo.upsert_incident(incident)
    repo.save_analysis(analysis)
    log(
        logger,
        logging.INFO,
        "incident ingested",
        incident_id=incident.id,
        adapter=adapter.name,
        events=len(incident.events),
        category=analysis.failure_category.value,
    )
    return incident, analysis
