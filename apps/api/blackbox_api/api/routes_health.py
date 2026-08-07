from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from blackbox_api.ai.explain import ai_provider
from blackbox_api.analysis.engine import ENGINE_VERSION
from blackbox_api.schemas import SCHEMA_VERSION
from blackbox_api.storage.db import get_db
from blackbox_api.storage.models import IncidentRow

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str | int]:
    db.execute(text("SELECT 1"))
    incident_count = len(db.scalars(select(IncidentRow.id)).all())
    return {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "incidents": incident_count,
        "ai_explanations": ai_provider() or "disabled",
    }
