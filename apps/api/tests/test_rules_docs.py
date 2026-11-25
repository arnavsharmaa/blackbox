"""Keeps docs/writing-rules.md complete: every IncidentFeatures field
a rule can score against must appear in the feature table."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from blackbox_api.analysis.features import IncidentFeatures

DOC = (
    Path(__file__).resolve().parents[3] / "docs" / "writing-rules.md"
).read_text()


def test_every_feature_is_documented() -> None:
    missing = [
        field.name
        for field in dataclasses.fields(IncidentFeatures)
        if f"`{field.name}`" not in DOC
    ]
    assert missing == [], f"undocumented features: {missing}"
