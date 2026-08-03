"""Adapter interface for turning external recordings into canonical Incidents.

Every ingestion path (seeded JSON, uploaded JSON, normalized CSV, and — in the
future — rosbag2) implements IncidentAdapter. Adapters are pure: bytes in,
validated Incident out. Persistence and analysis happen in the ingestion
service, never inside an adapter.

See robotics/adapters/README.md for the ROS2 topic mapping that a rosbag2
adapter would implement against this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from blackbox_api.schemas import Incident


class IngestError(Exception):
    """Raised when a payload cannot be converted into a valid Incident.

    ``details`` carries machine-readable validation errors suitable for
    returning to API clients.
    """

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class IncidentAdapter(ABC):
    """Converts one external format into the canonical Incident schema."""

    #: Short identifier, e.g. "json", "csv", "rosbag2".
    name: str = "base"
    #: File extensions (lowercase, with dot) this adapter accepts.
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, raw: bytes, *, metadata: dict[str, Any] | None = None) -> Incident:
        """Parse raw bytes into a validated Incident.

        ``metadata`` supplies incident-level fields for formats (like CSV
        event streams) that do not embed them.

        Raises IngestError with useful, field-level details on bad input.
        """
