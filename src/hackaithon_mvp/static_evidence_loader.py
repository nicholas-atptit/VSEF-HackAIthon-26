"""Static evidence loading and validation for the HackAIthon MVP.

The loader only validates local JSON records. It does not execute model logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model_diagnostics.inventory import EXCLUDED_FROM_MVP
from .model_diagnostics.registry import get_adapter

DEFAULT_SAMPLE_EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "examples" / "hackaithon_mvp" / "sample_evidence.json"
REQUIRED_FIELDS = {"model_key", "model_family", "model_display_name"}
METADATA_ONLY_EXECUTION_MODE = "metadata_only_static_demo"


class StaticEvidenceValidationError(ValueError):
    """Raised when a static evidence record violates the MVP metadata contract."""


def _contains_excluded_token(value: object) -> bool:
    lowered = str(value).lower()
    return any(token in lowered for token in EXCLUDED_FROM_MVP)


def validate_evidence_record(record: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS.difference(record))
    if missing:
        raise StaticEvidenceValidationError(f"missing required fields: {missing}")
    if _contains_excluded_token(record["model_key"]) or _contains_excluded_token(record["model_family"]):
        raise StaticEvidenceValidationError("excluded model family or key is not valid for this MVP")
    try:
        adapter = get_adapter(str(record["model_key"]))
    except KeyError as exc:
        raise StaticEvidenceValidationError(f"unknown model_key: {record['model_key']}") from exc

    metadata = adapter.to_metadata()
    if record["model_family"] != metadata["model_family"]:
        raise StaticEvidenceValidationError(
            f"model_family mismatch for {record['model_key']}: {record['model_family']} != {metadata['model_family']}"
        )
    if record["model_display_name"] != metadata["display_name"]:
        raise StaticEvidenceValidationError(
            f"model_display_name mismatch for {record['model_key']}: {record['model_display_name']} != {metadata['display_name']}"
        )
    if metadata["dependency_status"] in {"missing_dependency", "optional_dependency"}:
        execution_mode = record.get("execution_mode")
        if execution_mode != METADATA_ONLY_EXECUTION_MODE:
            raise StaticEvidenceValidationError(
                f"dependency-gated model {record['model_key']} must use {METADATA_ONLY_EXECUTION_MODE}"
            )

    validated = dict(record)
    validated["adapter_dependency_status"] = metadata["dependency_status"]
    validated["adapter_is_exploratory"] = metadata["is_exploratory"]
    return validated


def validate_evidence_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [validate_evidence_record(record) for record in records]


def load_static_evidence(path: str | Path | None = None) -> list[dict[str, Any]]:
    evidence_path = Path(path) if path is not None else DEFAULT_SAMPLE_EVIDENCE_PATH
    with evidence_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise StaticEvidenceValidationError("static evidence payload must be a list")
    if not all(isinstance(record, dict) for record in payload):
        raise StaticEvidenceValidationError("each static evidence record must be an object")
    return validate_evidence_records(payload)
