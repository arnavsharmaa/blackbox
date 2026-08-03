from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from blackbox_api.ingestion.base import IncidentAdapter, IngestError
from blackbox_api.schemas import Incident


def format_validation_error(exc: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "field": ".".join(str(p) for p in err["loc"]) or "<root>",
            "error": err["msg"],
            "input_preview": _preview(err.get("input")),
        }
        for err in exc.errors(include_url=False)
    ]


def _preview(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


class JsonIncidentAdapter(IncidentAdapter):
    name = "json"
    extensions = (".json",)

    def parse(self, raw: bytes, *, metadata: dict[str, Any] | None = None) -> Incident:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IngestError(
                f"file is not valid JSON: {exc.msg} (line {exc.lineno}, "
                f"column {exc.colno})"
            ) from exc
        if not isinstance(data, dict):
            raise IngestError(
                "expected a JSON object matching the incident schema, got "
                f"{type(data).__name__}"
            )
        if metadata:
            data = {**data, **metadata}
        try:
            return Incident.model_validate(data)
        except ValidationError as exc:
            raise IngestError(
                "incident failed schema validation",
                details=format_validation_error(exc),
            ) from exc
