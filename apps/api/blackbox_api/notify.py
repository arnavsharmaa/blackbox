"""Webhook notifications for ingested and resolved incidents.

Set BLACKBOX_WEBHOOK_URL and every persisted incident (uploads and
stream cuts alike) POSTs a JSON payload there, as does every triage
transition to resolved. The payload carries a
Slack-compatible "text" line plus structured fields, so it works with
Slack/Mattermost incoming webhooks and custom receivers alike.

Delivery is best-effort by design: a slow or failing webhook must never
fail or stall an ingest, so errors are logged and swallowed and the
request uses a short timeout.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from blackbox_api.config import get_settings
from blackbox_api.logging import log
from blackbox_api.schemas import AnalysisResult, Incident

logger = logging.getLogger("blackbox.notify")

_TIMEOUT_S = 3.0


def _deliver(payload: dict[str, object], incident_id: str) -> None:
    """POST to the configured webhook; best-effort, errors swallowed."""
    url = get_settings().webhook_url
    if not url:
        return
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S):
            pass
        log(
            logger,
            logging.INFO,
            "webhook notified",
            incident_id=incident_id,
        )
    except (urllib.error.URLError, OSError) as exc:
        log(
            logger,
            logging.WARNING,
            "webhook delivery failed",
            incident_id=incident_id,
            error=str(exc),
        )


def notify_incident(
    incident: Incident, analysis: AnalysisResult, occurrence: int = 1
) -> None:
    category = analysis.failure_category.value
    recurrence_note = (
        f" — occurrence #{occurrence} of this failure signature"
        if occurrence >= 2
        else ""
    )
    _deliver({
        "text": (
            f"BlackBox: {incident.robot_id} — {incident.task_name} "
            f"({incident.outcome.value}); diagnosed {category} "
            f"at {analysis.confidence:.0%} confidence [{incident.id}]"
            f"{recurrence_note}"
        ),
        "event": "incident_ingested",
        "occurrence": occurrence,
        "incident_id": incident.id,
        "robot_id": incident.robot_id,
        "facility": incident.facility,
        "task_name": incident.task_name,
        "outcome": incident.outcome.value,
        "severity": incident.severity.value,
        "failure_category": category,
        "confidence": analysis.confidence,
        "start_time": incident.start_time.isoformat(),
    }, incident.id)


def notify_resolved(incident: Incident, hours_open: float | None) -> None:
    """Announce a resolution so the channel that saw the incident
    land also sees it closed out, with how long that took."""
    after = f" after {hours_open:.1f} h" if hours_open is not None else ""
    _deliver({
        "text": (
            f"BlackBox: {incident.id} resolved{after} — "
            f"{incident.task_name} ({incident.robot_id})"
        ),
        "event": "incident_resolved",
        "incident_id": incident.id,
        "robot_id": incident.robot_id,
        "facility": incident.facility,
        "task_name": incident.task_name,
        "hours_open": hours_open,
    }, incident.id)
