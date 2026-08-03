"""Incident report generation (structured JSON + Markdown)."""

from __future__ import annotations

from typing import Any

from blackbox_api.analysis.features import event_t
from blackbox_api.schemas import (
    AnalysisResult,
    EventType,
    Incident,
    Severity,
)

KEY_EVENT_TYPES = {
    EventType.TASK_STARTED,
    EventType.NAV_GOAL_ISSUED,
    EventType.PLANNER_STATE_CHANGED,
    EventType.RECOVERY_STARTED,
    EventType.RECOVERY_COMPLETED,
    EventType.WARNING_RAISED,
    EventType.ERROR_RAISED,
    EventType.TASK_TIMED_OUT,
    EventType.TASK_FAILED,
}

CATEGORY_LABELS = {
    "persistent_obstacle": "Persistent obstacle blockage",
    "localization_failure": "Localization failure",
    "controller_oscillation": "Controller oscillation",
    "sensor_dropout": "Sensor dropout",
    "unknown": "Unknown / needs manual review",
}


def _telemetry_extremes(incident: Incident) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for series in incident.telemetry:
        numeric = [
            float(s.value) for s in series.samples if isinstance(s.value, (int, float))
        ]
        if not numeric:
            continue
        rows.append(
            {
                "channel": series.channel.value,
                "unit": series.unit,
                "min": round(min(numeric), 3),
                "max": round(max(numeric), 3),
                "last": round(numeric[-1], 3),
                "samples": len(numeric),
            }
        )
    return rows


def build_report(incident: Incident, analysis: AnalysisResult | None) -> dict[str, Any]:
    key_events = [
        {
            "t": round(event_t(incident, ev), 2),
            "timestamp": ev.timestamp.isoformat(),
            "event_type": ev.event_type.value,
            "subsystem": ev.subsystem.value,
            "severity": ev.severity.value,
            "message": ev.message,
        }
        for ev in incident.events
        if ev.event_type in KEY_EVENT_TYPES
        or ev.severity in (Severity.ERROR, Severity.CRITICAL)
    ]
    return {
        "report_version": "1.0",
        "incident": {
            "id": incident.id,
            "robot_id": incident.robot_id,
            "robot_model": incident.robot_model,
            "facility": incident.facility,
            "environment": incident.environment,
            "task_name": incident.task_name,
            "task_goal": incident.task_goal,
            "start_time": incident.start_time.isoformat(),
            "end_time": incident.end_time.isoformat(),
            "duration_s": round(incident.duration_s, 2),
            "outcome": incident.outcome.value,
            "severity": incident.severity.value,
            "software_version": incident.software_version,
            "map_version": incident.map_version,
            "summary": incident.summary,
            "event_count": len(incident.events),
        },
        "root_cause": (
            {
                "category": analysis.failure_category.value,
                "category_label": CATEGORY_LABELS.get(
                    analysis.failure_category.value, analysis.failure_category.value
                ),
                "confidence": analysis.confidence,
                "explanation": analysis.explanation,
                "rules_triggered": analysis.rules_triggered,
                "engine_version": analysis.engine_version,
            }
            if analysis
            else None
        ),
        "evidence": (
            [e.model_dump(mode="json") for e in analysis.evidence] if analysis else []
        ),
        "recommended_actions": analysis.recommended_actions if analysis else [],
        "alternative_causes": (
            [a.model_dump(mode="json") for a in analysis.alternative_causes]
            if analysis
            else []
        ),
        "timeline": key_events,
        "telemetry_summary": _telemetry_extremes(incident),
        "reproduction": {
            "notes": (
                f"Replay incident {incident.id} in BlackBox to step through the "
                f"recorded telemetry deterministically. To reproduce on hardware "
                f"or simulation: load map {incident.map_version}, start robot "
                f"{incident.robot_id} ({incident.robot_model}) on software "
                f"{incident.software_version}, and re-issue task "
                f"'{incident.task_name}' with the same goal."
            ),
            "replay_url": f"/incidents/{incident.id}",
        },
        "ai_explanation": analysis.ai_explanation if analysis else None,
    }


def report_markdown(incident: Incident, analysis: AnalysisResult | None) -> str:
    r = build_report(incident, analysis)
    inc = r["incident"]
    lines: list[str] = []
    add = lines.append
    add(f"# Incident Report — {inc['id']}")
    add("")
    add("## Executive summary")
    add("")
    add(inc["summary"])
    if r["root_cause"]:
        rc = r["root_cause"]
        add("")
        add(
            f"**Root cause:** {rc['category_label']} "
            f"(confidence {rc['confidence'] * 100:.0f}%)"
        )
        add("")
        add(rc["explanation"])
    add("")
    add("## Incident metadata")
    add("")
    add("| Field | Value |")
    add("| --- | --- |")
    for label, key in [
        ("Robot", "robot_id"),
        ("Model", "robot_model"),
        ("Facility", "facility"),
        ("Environment", "environment"),
        ("Task", "task_name"),
        ("Goal", "task_goal"),
        ("Start", "start_time"),
        ("End", "end_time"),
        ("Duration (s)", "duration_s"),
        ("Outcome", "outcome"),
        ("Severity", "severity"),
        ("Software", "software_version"),
        ("Map", "map_version"),
        ("Events recorded", "event_count"),
    ]:
        add(f"| {label} | {inc[key]} |")
    if r["evidence"]:
        add("")
        add("## Evidence")
        add("")
        for e in r["evidence"]:
            anchor = f"t={e['t']:.1f}s"
            if e.get("t_end") is not None:
                anchor += f"–{e['t_end']:.1f}s"
            add(f"- **[{anchor}]** {e['summary']}")
    if r["recommended_actions"]:
        add("")
        add("## Recommended actions")
        add("")
        for i, action in enumerate(r["recommended_actions"], 1):
            add(f"{i}. {action}")
    if r["alternative_causes"]:
        add("")
        add("## Alternative causes considered")
        add("")
        for a in r["alternative_causes"]:
            add(
                f"- {CATEGORY_LABELS.get(a['category'], a['category'])} "
                f"(score {a['score'] * 100:.0f}%): {a['reason']}"
            )
    add("")
    add("## Key timeline")
    add("")
    add("| t (s) | Type | Subsystem | Severity | Message |")
    add("| --- | --- | --- | --- | --- |")
    for ev in r["timeline"]:
        add(
            f"| {ev['t']:.1f} | {ev['event_type']} | {ev['subsystem']} | "
            f"{ev['severity']} | {ev['message']} |"
        )
    if r["telemetry_summary"]:
        add("")
        add("## Telemetry summary")
        add("")
        add("| Channel | Unit | Min | Max | Last | Samples |")
        add("| --- | --- | --- | --- | --- | --- |")
        for t in r["telemetry_summary"]:
            add(
                f"| {t['channel']} | {t['unit']} | {t['min']} | {t['max']} | "
                f"{t['last']} | {t['samples']} |"
            )
    add("")
    add("## Reproduction notes")
    add("")
    add(r["reproduction"]["notes"])
    if r.get("ai_explanation"):
        add("")
        add("## AI-generated explanation")
        add("")
        add(
            "> ⚠️ The following summary was generated by an LLM from the "
            "deterministic analysis above. It did not influence the diagnosis."
        )
        add("")
        add(r["ai_explanation"])
    add("")
    return "\n".join(lines)
