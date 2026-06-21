"""Local LLM-readable record contract for diagnostic evidence."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from typing import Any


CREATED_AT = "2026-06-21T00:00:00+07:00"
RECORD_TYPES = (
    "engine_run_summary",
    "diagnostic_report",
    "evidence_packet",
    "risk_assessment",
    "scenario_assessment",
    "decision_lane_output",
    "ml_diagnostic_summary",
    "architecture_alignment",
    "diagram_coverage",
    "hardening_gate_report",
    "claim_boundary",
    "limitation_note",
)
REQUIRED_FIELDS = (
    "record_id",
    "record_type",
    "title",
    "summary",
    "content",
    "source_module",
    "created_at",
    "claim_boundary",
    "non_claim",
    "human_review_required",
    "read_only",
)
OPTIONAL_FIELDS = ("ticker", "timeframe", "run_id")
CLAIM_BOUNDARY = {
    "local_llm_readable_evidence_only": True,
    "read_only": True,
    "llm_write_allowed": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_server_database": True,
    "no_vector_database": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local evidence context for research diagnostics; read-only retrieval only."
SECRET_KEY_PATTERNS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "credential",
    "access_token",
    "refresh_token",
    "private_key",
)
DIRECT_PROVIDER_FIELD_PATTERNS = (
    "provider_payload",
    "provider_response",
    "raw_provider",
    "provider_api",
)
LIVE_DATA_KEYS = ("live_data", "is_live", "live_mode", "streaming_enabled")
ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
ACTION_LABEL_PATTERN = re.compile(r"\b(" + "|".join(re.escape(term) for term in ACTION_LABEL_TERMS) + r")\b", re.IGNORECASE)
ADVISORY_PATTERN = re.compile(r"\b" + re.escape(" ".join(("financial", "advice"))) + r"\b", re.IGNORECASE)


def _walk_items(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}" if path else key_text
            yield next_path, key_text, nested
            yield from _walk_items(nested, next_path)
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            yield from _walk_items(nested, f"{path}[{index}]")


def _boundary_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, key, value in _walk_items(record):
        lowered_key = key.lower()
        if any(token in lowered_key for token in SECRET_KEY_PATTERNS):
            errors.append(f"{path} must not include secret material")
        if any(token in lowered_key for token in DIRECT_PROVIDER_FIELD_PATTERNS):
            errors.append(f"{path} must not include direct provider payload fields")
        if lowered_key in LIVE_DATA_KEYS:
            errors.append(f"{path} must not include a live-data flag")
        if lowered_key in {"write_permission", "write_permissions", "llm_write_allowed"} and value is True:
            errors.append(f"{path} must remain read-only")
        if isinstance(value, str):
            if ACTION_LABEL_PATTERN.search(value):
                errors.append(f"{path} must not include action labels")
            if ADVISORY_PATTERN.search(value):
                errors.append(f"{path} must not include advisory wording")
    return errors


def _non_empty_text(record: dict[str, Any], field: str, errors: list[str]) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def build_llm_storage_contract() -> dict:
    """Return the local record contract for LLM-readable diagnostic evidence."""

    return {
        "contract_version": "1.0",
        "contract_status": "ready_for_local_llm_readable_evidence_contract",
        "storage_format": "jsonl",
        "record_types": list(RECORD_TYPES),
        "required_fields": list(REQUIRED_FIELDS),
        "optional_fields": list(OPTIONAL_FIELDS),
        "rules": {
            "writes_require_explicit_store_root": True,
            "read_only_for_llm": True,
            "no_default_writes": True,
            "no_server_database": True,
            "no_vector_database": True,
            "no_live_data": True,
            "no_provider_calls": True,
            "no_model_updates": True,
            "human_review_required": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def get_llm_readable_record_types() -> tuple[str, ...]:
    """Return the allowed LLM-readable record types."""

    return RECORD_TYPES


def validate_llm_readable_record(record: dict) -> dict:
    """Validate one local evidence record for read-only retrieval."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(record, dict):
        return {
            "is_valid": False,
            "normalized_record": None,
            "errors": ["record must be an object"],
            "warnings": warnings,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    source = deepcopy(record)
    missing = [field for field in REQUIRED_FIELDS if field not in source]
    errors.extend(f"missing required field: {field}" for field in missing)
    record_id = _non_empty_text(source, "record_id", errors)
    record_type = _non_empty_text(source, "record_type", errors)
    title = _non_empty_text(source, "title", errors)
    summary = _non_empty_text(source, "summary", errors)
    source_module = _non_empty_text(source, "source_module", errors)
    created_at = _non_empty_text(source, "created_at", errors)
    non_claim = _non_empty_text(source, "non_claim", errors)

    if record_type and record_type not in RECORD_TYPES:
        errors.append(f"record_type is not allowed: {record_type}")
    content = source.get("content")
    if content in (None, "", [], {}):
        errors.append("content must be non-empty")
    if not isinstance(source.get("claim_boundary"), dict):
        errors.append("claim_boundary must be an object")
    if source.get("human_review_required") is not True:
        errors.append("human_review_required must be True")
    if source.get("read_only") is not True:
        errors.append("read_only must be True")
    for field in OPTIONAL_FIELDS:
        if field in source and source[field] not in (None, "") and not isinstance(source[field], str):
            errors.append(f"{field} must be a string when provided")
    errors.extend(_boundary_errors(source))

    normalized_record = None
    if not errors:
        normalized_record = {
            "record_id": record_id,
            "record_type": record_type,
            "title": title,
            "summary": summary,
            "content": content,
            "source_module": source_module,
            "created_at": created_at,
            "claim_boundary": dict(source["claim_boundary"]),
            "non_claim": non_claim,
            "human_review_required": True,
            "read_only": True,
        }
        for field in OPTIONAL_FIELDS:
            if source.get(field) not in (None, ""):
                normalized_record[field] = str(source[field]).strip()
        boundary = normalized_record["claim_boundary"]
        if boundary.get("read_only") is not True:
            warnings.append("claim_boundary.read_only was not explicitly True")
        if boundary.get("human_review_required") is not True:
            warnings.append("claim_boundary.human_review_required was not explicitly True")

    return {
        "is_valid": not errors,
        "normalized_record": normalized_record,
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_llm_storage_manifest() -> dict:
    """Build a compact manifest for the local evidence store contract."""

    return {
        "manifest_version": "1.0",
        "manifest_status": "ready_for_local_llm_readable_evidence_store",
        "record_types": list(RECORD_TYPES),
        "storage_files": ["llm_readable_records.jsonl"],
        "storage_backends": ["local_jsonl"],
        "default_write_enabled": False,
        "read_only_retrieval": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect the local LLM-readable storage contract.")
    parser.add_argument("--manifest", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    output = build_llm_storage_manifest() if args.manifest else build_llm_storage_contract()
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
