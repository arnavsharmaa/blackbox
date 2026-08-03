from blackbox_api.ingestion.base import IncidentAdapter, IngestError
from blackbox_api.ingestion.csv_adapter import CsvIncidentAdapter
from blackbox_api.ingestion.json_adapter import JsonIncidentAdapter
from blackbox_api.ingestion.service import adapter_for_filename, ingest_incident

__all__ = [
    "IncidentAdapter",
    "IngestError",
    "CsvIncidentAdapter",
    "JsonIncidentAdapter",
    "adapter_for_filename",
    "ingest_incident",
]
