from __future__ import annotations

import sys
import types

import pytest

from blackbox_api.ai.explain import _validate_summary, ai_provider
from blackbox_api.analysis.engine import analyze_incident
from blackbox_api.schemas import Incident


@pytest.fixture()
def obstacle_analysis(parsed_incidents: dict[str, Incident]):
    return analyze_incident(parsed_incidents["obstacle"])


def _fake_module() -> types.ModuleType:
    return types.ModuleType("fake_sdk")


def test_no_keys_means_no_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ai_provider() is None


def test_anthropic_preferred_when_both_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "anthropic", _fake_module())
    monkeypatch.setitem(sys.modules, "openai", _fake_module())
    assert ai_provider() == "anthropic"


def test_openai_used_when_anthropic_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # A None entry in sys.modules makes `import anthropic` raise ImportError.
    monkeypatch.setitem(sys.modules, "anthropic", None)  # type: ignore[arg-type]
    monkeypatch.setitem(sys.modules, "openai", _fake_module())
    assert ai_provider() == "openai"


def test_key_without_sdk_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "anthropic", None)  # type: ignore[arg-type]
    assert ai_provider() is None


def test_validate_summary_accepts_on_topic_text(obstacle_analysis) -> None:
    text = (
        "The robot stopped because a persistent obstacle blocked the aisle "
        "and recovery behaviors could not clear it."
    )
    assert _validate_summary(text, obstacle_analysis) == text


def test_validate_summary_rejects_empty_and_oversized(
    obstacle_analysis,
) -> None:
    assert _validate_summary("", obstacle_analysis) is None
    assert _validate_summary("   ", obstacle_analysis) is None
    assert _validate_summary("x" * 5000, obstacle_analysis) is None


def test_validate_summary_rejects_off_category_text(obstacle_analysis) -> None:
    # A summary that never mentions the diagnosed category is discarded.
    assert (
        _validate_summary(
            "The battery ran out and the robot shut down.", obstacle_analysis
        )
        is None
    )
