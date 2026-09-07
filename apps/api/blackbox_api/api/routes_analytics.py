from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from blackbox_api.analytics import AnalyticsResponse, compute_analytics
from blackbox_api.api.auth import TokenScope, get_token_scope
from blackbox_api.storage.db import get_db
from blackbox_api.storage.repository import IncidentRepository

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[TokenScope, Depends(get_token_scope)],
    facility: str | None = None,
    start_after: datetime | None = None,
    start_before: datetime | None = None,
) -> AnalyticsResponse:
    """Fleet analytics, scoped to the token's facility when limited.

    start_after/start_before window the aggregation (e.g. "this week"),
    except calibration, which always reflects all engineer verdicts.
    """
    return compute_analytics(
        IncidentRepository(db),
        facility=scope.facility or facility,
        start_after=start_after,
        start_before=start_before,
    )
