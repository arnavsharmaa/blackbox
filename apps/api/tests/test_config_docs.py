"""Keeps docs/configuration.md complete: every settings field must
appear there under its environment-variable name."""

from __future__ import annotations

from pathlib import Path

from blackbox_api.analysis.thresholds import AnalysisThresholds
from blackbox_api.config import Settings

DOC = (
    Path(__file__).resolve().parents[3] / "docs" / "configuration.md"
).read_text()


def test_every_core_setting_is_documented() -> None:
    missing = [
        f"BLACKBOX_{name.upper()}"
        for name in Settings.model_fields
        if f"`BLACKBOX_{name.upper()}`" not in DOC
    ]
    assert missing == [], f"undocumented settings: {missing}"


def test_every_threshold_is_documented() -> None:
    missing = [
        f"BLACKBOX_RULE_{name.upper()}"
        for name in AnalysisThresholds.model_fields
        if f"`BLACKBOX_RULE_{name.upper()}`" not in DOC
    ]
    assert missing == [], f"undocumented thresholds: {missing}"
