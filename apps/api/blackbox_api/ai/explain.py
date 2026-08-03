"""Optional AI explanation layer.

Converts the deterministic AnalysisResult into a short prose summary using the
Anthropic API when ANTHROPIC_API_KEY is set (install with `pip install
'blackbox-api[ai]'`). The LLM never determines the root cause — it may only
restate facts present in the structured analysis, and its output is validated
before being attached. When no key or SDK is available, callers fall back to
the deterministic explanation.
"""

from __future__ import annotations

import logging
import os

from blackbox_api.logging import log
from blackbox_api.schemas import AnalysisResult, Incident

logger = logging.getLogger("blackbox.ai")

MODEL = "claude-opus-5"
MAX_SUMMARY_CHARS = 2000

SYSTEM_PROMPT = (
    "You summarize robot incident analyses for engineers. You will receive a "
    "deterministic root-cause analysis produced by a rules engine, including "
    "its evidence. Write a concise (3-5 sentence) plain-English summary of "
    "what happened and why. Hard constraints: use ONLY facts present in the "
    "provided analysis; do not speculate, introduce new causes, numbers, or "
    "conclusions not supported by the listed evidence; do not contradict the "
    "stated failure category. Respond with the summary text only."
)


def ai_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _build_prompt(incident: Incident, analysis: AnalysisResult) -> str:
    evidence_lines = "\n".join(
        f"- [t={e.t:.1f}s] {e.summary}" for e in analysis.evidence
    )
    alternatives = "\n".join(
        f"- {a.category.value} (score {a.score:.0%}): {a.reason}"
        for a in analysis.alternative_causes
    )
    return (
        f"Incident {incident.id}: robot {incident.robot_id} "
        f"({incident.robot_model}) at {incident.facility}.\n"
        f"Task: {incident.task_name} — {incident.task_goal}\n"
        f"Outcome: {incident.outcome.value}, severity {incident.severity.value}, "
        f"duration {incident.duration_s:.0f}s.\n\n"
        f"Deterministic diagnosis: {analysis.failure_category.value} "
        f"(confidence {analysis.confidence:.0%}).\n"
        f"Engine explanation: {analysis.explanation}\n\n"
        f"Evidence:\n{evidence_lines}\n\n"
        f"Alternative causes considered:\n{alternatives or '- none'}"
    )


def _validate_summary(text: str, analysis: AnalysisResult) -> str | None:
    """Reject empty, oversized, or off-topic model output."""
    text = text.strip()
    if not text or len(text) > MAX_SUMMARY_CHARS:
        return None
    # The summary must stay anchored to the deterministic category: require a
    # keyword from the diagnosed category to appear.
    keywords = {
        "persistent_obstacle": ("obstacle", "blocked", "blockage"),
        "localization_failure": ("localization", "pose", "position estimate"),
        "controller_oscillation": ("oscillat", "controller", "angular"),
        "sensor_dropout": ("sensor", "lidar", "dropout", "stale"),
        "unknown": ("unknown", "manual", "inconclusive", "review"),
    }[analysis.failure_category.value]
    if not any(k in text.lower() for k in keywords):
        return None
    return text


def generate_ai_explanation(
    incident: Incident, analysis: AnalysisResult
) -> str | None:
    """Return a validated AI summary, or None if unavailable/invalid."""
    if not ai_available():
        return None
    import anthropic

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(incident, analysis)}],
        )
    except anthropic.APIError as exc:
        log(logger, logging.WARNING, "AI explanation failed", error=str(exc))
        return None
    if response.stop_reason == "refusal":
        log(logger, logging.WARNING, "AI explanation refused")
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    summary = _validate_summary(text, analysis)
    if summary is None:
        log(logger, logging.WARNING, "AI explanation failed validation")
        return None
    return summary
