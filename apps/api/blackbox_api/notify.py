"""Webhook notification for newly ingested incidents.

Set BLACKBOX_WEBHOOK_URL and every persisted incident (uploads and
stream cuts alike) POSTs a JSON payload there. The payload carries a
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


def notify_incident(incident: Incident, analysis: AnalysisResult) -> None:
    url = get_settings().webhook_url
    if not url:
        return
    category = analysis.failure_category.value
    payload = {
        "text": (
            f"BlackBox: {incident.robot_id} — {incident.task_name} "
            f"({incident.outcome.value}); diagnosed {category} "
            f"at {analysis.confidence:.0%} confidence [{incident.id}]"
        ),
        "incident_id": incident.id,
        "robot_id": incident.robot_id,
        "facility": incident.facility,
        "task_name": incident.task_name,
        "outcome": incident.outcome.value,
        "severity": incident.severity.value,
        "failure_category": category,
        "confidence": analysis.confidence,
        "start_time": incident.start_time.isoformat(),
    }
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
            incident_id=incident.id,
        )
    except (urllib.error.URLError, OSError) as exc:
        log(
            logger,
            logging.WARNING,
            "webhook delivery failed",
            incident_id=incident.id,
            error=str(exc),
        )
