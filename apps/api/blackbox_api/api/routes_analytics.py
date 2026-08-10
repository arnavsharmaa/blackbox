from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from blackbox_api.analytics import AnalyticsResponse, compute_analytics
from blackbox_api.storage.db import get_db
from blackbox_api.storage.repository import IncidentRepository

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Annotated[Session, Depends(get_db)]) -> AnalyticsResponse:
    return compute_analytics(IncidentRepository(db))
