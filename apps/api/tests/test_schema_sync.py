"""Guards against drift between the Pydantic schema and its TS mirror."""

from __future__ import annotations

import re
from pathlib import Path

from blackbox_api.schemas import (
    EventType,
    FailureCategory,
    FeedbackVerdict,
    Incident,
    Outcome,
    Severity,
    Subsystem,
    TelemetryChannel,
)

TS_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "schemas"
    / "src"
    / "incident.ts"
)


def _ts_union_values(type_name: str) -> set[str]:
    source = TS_PATH.read_text()
    match = re.search(
        rf"export type {type_name} =\s*(.+?);", source, re.DOTALL
    )
    assert match, f"type {type_name} not found in incident.ts"
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def test_enum_values_match_typescript() -> None:
    pairs = [
        ("Severity", Severity),
        ("Outcome", Outcome),
        ("FailureCategory", FailureCategory),
        ("Subsystem", Subsystem),
        ("EventType", EventType),
        ("TelemetryChannel", TelemetryChannel),
        ("FeedbackVerdict", FeedbackVerdict),
    ]
    for ts_name, py_enum in pairs:
        assert _ts_union_values(ts_name) == {m.value for m in py_enum}, ts_name


def test_incident_fields_match_typescript() -> None:
    source = TS_PATH.read_text()
    match = re.search(
        r"export interface Incident \{(.+?)\}", source, re.DOTALL
    )
    assert match
    ts_fields = set(re.findall(r"^\s*(\w+):", match.group(1), re.MULTILINE))
    py_fields = set(Incident.model_fields.keys())
    assert ts_fields == py_fields
