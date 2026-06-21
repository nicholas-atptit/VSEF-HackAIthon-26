"""Schema contract for future social context signals."""

from __future__ import annotations

import argparse
import json
from typing import Any


ALLOWED_SOURCE_TYPES = ("news", "filing", "social", "forum", "manual_note")
ALLOWED_SIGNAL_CATEGORIES = (
    "positive_context",
    "negative_context",
    "uncertain_context",
    "volume_spike",
    "unverified",
)
SCHEMA_FIELDS = (
    "ticker",
    "timestamp",
    "source_type",
    "signal_category",
    "sentiment_score",
    "confidence",
    "evidence_reference",
    "human_review_required",
)
NON_CLAIM_TEXT = "Social context schema contract only; human review remains required."
CLAIM_BOUNDARY = {
    "contract_only": True,
    "api_calls_enabled": False,
    "scraping_enabled": False,
    "social_ingestion_enabled": False,
    "sentiment_model_enabled": False,
    "live_data_enabled": False,
    "writes_files": False,
    "human_review_required": True,
}


def get_social_listening_contract() -> dict:
    """Return the future social context signal schema contract."""

    return {
        "contract_status": "schema_contract_only",
        "schema_fields": list(SCHEMA_FIELDS),
        "allowed_source_type": list(ALLOWED_SOURCE_TYPES),
        "allowed_signal_category": list(ALLOWED_SIGNAL_CATEGORIES),
        "required_flags": {"human_review_required": True},
        "runtime_boundary": {
            "api_calls_enabled": False,
            "scraping_enabled": False,
            "social_ingestion_enabled": False,
            "sentiment_model_enabled": False,
            "live_data_enabled": False,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _number_in_range(value: Any, *, low: float, high: float, field_name: str) -> tuple[float | None, str | None]:
    if isinstance(value, bool) or value is None:
        return None, f"{field_name} must be numeric"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, f"{field_name} must be numeric"
    if number < low or number > high:
        return None, f"{field_name} must be between {low} and {high}"
    return number, None


def validate_social_signal_record(record: dict) -> dict:
    """Validate one future social context signal record against the contract."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(record, dict):
        return {"is_valid": False, "errors": ["record must be a dictionary"], "warnings": []}
    missing = [field for field in SCHEMA_FIELDS if field not in record]
    errors.extend(f"missing field: {field}" for field in missing)
    if record.get("source_type") not in ALLOWED_SOURCE_TYPES:
        errors.append("source_type is not allowed")
    if record.get("signal_category") not in ALLOWED_SIGNAL_CATEGORIES:
        errors.append("signal_category is not allowed")
    if not str(record.get("ticker", "")).strip():
        errors.append("ticker must be non-empty")
    if not str(record.get("timestamp", "")).strip():
        errors.append("timestamp must be non-empty")
    if not str(record.get("evidence_reference", "")).strip():
        warnings.append("evidence_reference is empty")
    _, score_error = _number_in_range(
        record.get("sentiment_score"),
        low=-1.0,
        high=1.0,
        field_name="sentiment_score",
    )
    if score_error:
        errors.append(score_error)
    _, confidence_error = _number_in_range(
        record.get("confidence"),
        low=0.0,
        high=1.0,
        field_name="confidence",
    )
    if confidence_error:
        errors.append(confidence_error)
    if record.get("human_review_required") is not True:
        errors.append("human_review_required must be True")
    return {
        "is_valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_empty_social_context() -> dict:
    """Build an empty local social context object."""

    return {
        "context_status": "empty_contract_context",
        "records": [],
        "record_count": 0,
        "api_calls_performed": False,
        "scraping_performed": False,
        "social_ingestion_performed": False,
        "sentiment_model_used": False,
        "live_data_used": False,
        "human_review_required": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Inspect the social context schema contract.")


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    parser.parse_args(argv)
    print(
        json.dumps(
            {
                "contract": get_social_listening_contract(),
                "empty_context": build_empty_social_context(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
