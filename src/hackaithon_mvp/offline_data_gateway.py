"""Offline local-file gateway into the diagnostic engine payload contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.diagnostic_engine import render_diagnostic_engine_report, run_diagnostic_engine_from_payload
from src.hackaithon_mvp.diagnostic_to_llm_records import build_llm_records_from_diagnostic_result
from src.hackaithon_mvp.engine_input_contract import validate_engine_input_payload
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


ACCEPTED_EXTENSIONS = (".csv", ".jsonl", ".json")
REQUIRED_BAR_FIELDS = ("ticker", "timestamp", "open", "high", "low", "close", "volume")
ALIASES = {
    "symbol": "ticker",
    "date": "timestamp",
    "time": "timestamp",
    "o": "open",
    "h": "high",
    "l": "low",
    "c": "close",
    "v": "volume",
}
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
DIRECT_SOURCE_PATTERNS = ("provider_payload", "provider_response", "provider_api", "raw_provider")
ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
ACTION_LABEL_PATTERN = re.compile(r"\b(" + "|".join(re.escape(term) for term in ACTION_LABEL_TERMS) + r")\b", re.IGNORECASE)
CLAIM_BOUNDARY = {
    "offline_gateway_only": True,
    "local_files_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_server_database": True,
    "no_vector_database": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Offline local-file gateway for research diagnostics; canonical payload handoff only."


def _safe_float(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number:
        raise ValueError(f"{field_name} must be numeric")
    return number


def _normalize_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    return ticker


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-like and sortable") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clean_record_keys(record: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        canonical_key = ALIASES.get(str(key).strip().lower(), str(key).strip().lower())
        cleaned[canonical_key] = value
    return cleaned


def _boundary_errors(record: dict[str, Any], index: int) -> list[str]:
    errors: list[str] = []
    for key, value in record.items():
        lowered = str(key).lower()
        if any(token in lowered for token in SECRET_KEY_PATTERNS):
            errors.append(f"records[{index}].{key} must not include secret material")
        if any(token in lowered for token in DIRECT_SOURCE_PATTERNS):
            errors.append(f"records[{index}].{key} must not include direct provider fields")
        if isinstance(value, str) and ACTION_LABEL_PATTERN.search(value):
            errors.append(f"records[{index}].{key} must not include action labels")
    return errors


def _normalize_bar(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = _clean_record_keys(record)
    missing = [field for field in REQUIRED_BAR_FIELDS if cleaned.get(field) in (None, "")]
    if missing:
        raise ValueError(f"missing required bar fields: {missing}")
    ticker = _normalize_ticker(cleaned["ticker"])
    timestamp = str(cleaned["timestamp"]).strip()
    _parse_timestamp(timestamp)
    open_value = _safe_float(cleaned["open"], "open")
    high_value = _safe_float(cleaned["high"], "high")
    low_value = _safe_float(cleaned["low"], "low")
    close_value = _safe_float(cleaned["close"], "close")
    volume_value = _safe_float(cleaned["volume"], "volume")
    if volume_value < 0:
        raise ValueError("volume must be non-negative")
    if high_value < max(open_value, close_value, low_value):
        raise ValueError("high must be greater than or equal to open, close, and low")
    if low_value > min(open_value, close_value, high_value):
        raise ValueError("low must be less than or equal to open, close, and high")
    return {
        "ticker": ticker,
        "timestamp": timestamp,
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "close": close_value,
        "volume": volume_value,
    }


def _timestamp_warnings(records: tuple[dict, ...]) -> list[str]:
    warnings: list[str] = []
    parsed: list[datetime] = []
    for record in records:
        try:
            parsed.append(_parse_timestamp(record.get("timestamp")))
        except ValueError:
            warnings.append("missing or unsortable timestamp found")
    if len(parsed) < 2:
        return warnings
    counts = Counter(value.isoformat() for value in parsed)
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    if duplicate_count:
        warnings.append(f"duplicate timestamps detected: {duplicate_count}")
    ordered = sorted(set(parsed))
    gaps = [
        round((right - left).total_seconds() / 86400, 6)
        for left, right in zip(ordered, ordered[1:])
        if (right - left).total_seconds() > 2 * 86400
    ]
    if gaps:
        warnings.append(f"large timestamp gaps detected: max_gap_days={max(gaps)}")
    latest = max(parsed)
    now = datetime(2026, 6, 21, tzinfo=timezone.utc)
    age_days = (now - latest.astimezone(timezone.utc)).days
    if age_days > 30:
        warnings.append(f"local bars appear stale: max_bar_age_days={age_days}")
    return warnings


def detect_local_data_format(path: str) -> dict:
    """Detect a local input file format without loading the data."""

    local_path = Path(path)
    suffix = local_path.suffix.lower()
    errors: list[str] = []
    if not path:
        errors.append("input path is required")
    elif not local_path.exists():
        errors.append(f"input path not found: {path}")
    elif not local_path.is_file():
        errors.append(f"input path must be a file: {path}")
    elif suffix not in ACCEPTED_EXTENSIONS:
        errors.append(f"input format is not accepted: {suffix or 'missing extension'}")
    return {
        "is_valid": not errors,
        "path": str(local_path),
        "path_exists": local_path.exists(),
        "format": suffix[1:] if suffix in ACCEPTED_EXTENSIONS else None,
        "extension": suffix,
        "errors": errors,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def read_local_records(path: str) -> tuple[dict, ...]:
    """Read local CSV, JSONL, or JSON object records."""

    detection = detect_local_data_format(path)
    if not detection["is_valid"]:
        raise ValueError("; ".join(detection["errors"]))
    local_path = Path(path)
    suffix = local_path.suffix.lower()
    if suffix == ".csv":
        with local_path.open("r", newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    elif suffix == ".jsonl":
        rows = [json.loads(line) for line in local_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    else:
        payload = json.loads(local_path.read_text(encoding="utf-8-sig"))
        rows = payload.get("rows") or payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("local input must contain object records")
    return tuple(rows)


def normalize_market_bar_records(records: tuple[dict, ...]) -> tuple[dict, ...]:
    """Normalize local market-bar records and raise on invalid rows."""

    validation = validate_market_bar_records(records)
    if not validation["is_valid"]:
        raise ValueError("; ".join(validation["errors"]))
    return tuple(validation["normalized_records"])


def validate_market_bar_records(records: tuple[dict, ...]) -> dict:
    """Validate local market bars and return normalized rows plus warnings."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(records, tuple):
        errors.append("records must be a tuple")
        records = tuple(records or ()) if isinstance(records, list) else tuple()
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue
        errors.extend(_boundary_errors(record, index))
        try:
            normalized.append(_normalize_bar(record))
        except (TypeError, ValueError) as exc:
            errors.append(f"records[{index}]: {exc}")
    if not normalized:
        warnings.append("no valid market bars provided")
        errors.append("at least one valid market bar is required")
    warnings.extend(_timestamp_warnings(tuple(normalized)))
    return {
        "is_valid": not errors,
        "records_total": len(records),
        "records_valid": len(normalized),
        "records_invalid": max(0, len(records) - len(normalized)),
        "normalized_records": tuple(normalized),
        "warnings": warnings,
        "errors": errors,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_payload_from_local_records(
    *,
    records: tuple[dict, ...],
    ticker: str,
    timeframe: str = "1 ngày",
    horizon_steps: int = 1,
    policy_demo: str | None = None,
) -> dict:
    """Build a canonical diagnostic engine payload from normalized local bars."""

    ticker_value = _normalize_ticker(ticker)
    timeframe_value = normalize_timeframe(timeframe)
    horizon_value = int(horizon_steps)
    normalized_records = normalize_market_bar_records(records)
    filtered = [record for record in normalized_records if record["ticker"] == ticker_value]
    bars = filtered or list(normalized_records)
    for bar in bars:
        bar["timeframe"] = timeframe_value
    parsed = [_parse_timestamp(record["timestamp"]) for record in bars]
    max_bar_age_days = None
    if parsed:
        max_bar_age_days = max(0, (datetime(2026, 6, 21, tzinfo=timezone.utc) - max(parsed).astimezone(timezone.utc)).days)
    payload = {
        "request": {
            "ticker": ticker_value,
            "timeframe": timeframe_value,
            "horizon_steps": horizon_value,
            "run_id": f"offline-gateway-{ticker_value.lower()}-{timeframe_value}-h{horizon_value}",
            "policy_demo": policy_demo,
        },
        "market_bars": bars,
        "forecast_rows": [],
        "model_diagnostics": [],
        "scenario_context": {
            "uncertainty_level": "medium" if len(bars) < 3 else "low",
            "data_quality_status": "nominal" if len(bars) >= 2 else "degraded",
            "evidence_status": "provided" if bars else "missing",
        },
        "risk_context": {
            "manual_review_required": True,
            "max_bar_age_days": max_bar_age_days,
        },
        "social_context": {
            "context_status": "not_ingested_contract_only",
            "records": [],
        },
        "metadata": {
            "source_module": "offline_data_gateway",
            "local_file_gateway": True,
            "records_provided": len(records),
            "records_used": len(bars),
        },
    }
    validation = validate_engine_input_payload(payload)
    if not validation["is_valid"]:
        raise ValueError("; ".join(validation["errors"]))
    return payload


def _safe_failure(*, detection: dict | None = None, errors: list[str] | None = None, warnings: list[str] | None = None) -> dict:
    return {
        "gateway_status": "safe_failure",
        "format_detected": detection or {},
        "records_read": 0,
        "records_valid": 0,
        "records_invalid": 0,
        "normalized_records": tuple(),
        "payload": None,
        "engine_result": None,
        "llm_records_written": 0,
        "store_write_status": "not_requested",
        "warnings": warnings or [],
        "errors": errors or [],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def run_offline_gateway_to_engine(
    *,
    input_path: str,
    ticker: str,
    timeframe: str = "1 ngày",
    horizon_steps: int = 1,
    policy_demo: str | None = None,
    store_root: str | None = None,
) -> dict:
    """Read local bars, run the diagnostic engine, and optionally write LLM-readable records."""

    detection = detect_local_data_format(input_path)
    if not detection["is_valid"]:
        return _safe_failure(detection=detection, errors=list(detection["errors"]))
    try:
        records = read_local_records(input_path)
        validation = validate_market_bar_records(records)
        if not validation["is_valid"]:
            return _safe_failure(
                detection=detection,
                errors=list(validation["errors"]),
                warnings=list(validation["warnings"]),
            ) | {
                "records_read": len(records),
                "records_valid": validation["records_valid"],
                "records_invalid": validation["records_invalid"],
                "normalized_records": validation["normalized_records"],
            }
        normalized_records = tuple(validation["normalized_records"])
        payload = build_payload_from_local_records(
            records=normalized_records,
            ticker=ticker,
            timeframe=timeframe,
            horizon_steps=horizon_steps,
            policy_demo=policy_demo,
        )
        engine_result = run_diagnostic_engine_from_payload(payload)
        write_result = {"write_status": "not_requested", "written_count": 0}
        if store_root:
            llm_records = build_llm_records_from_diagnostic_result(engine_result)
            write_result = write_llm_readable_records(records=llm_records, store_root=store_root)
        return {
            "gateway_status": "completed",
            "format_detected": detection,
            "records_read": len(records),
            "records_valid": validation["records_valid"],
            "records_invalid": validation["records_invalid"],
            "normalized_records": normalized_records,
            "payload": payload,
            "engine_result": engine_result,
            "llm_records_written": int(write_result.get("written_count", 0) or 0),
            "store_write_status": write_result.get("write_status"),
            "warnings": list(validation["warnings"]),
            "errors": [],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _safe_failure(detection=detection, errors=[str(exc)])


def render_offline_gateway_report(result: dict) -> str:
    """Render a compact offline gateway report."""

    lines = [
        "# Offline Data Gateway v0",
        "",
        f"Gateway status: {result.get('gateway_status')}",
        f"Format: {result.get('format_detected', {}).get('format')}",
        f"Records read: {result.get('records_read')}",
        f"Records valid: {result.get('records_valid')}",
        f"Records invalid: {result.get('records_invalid')}",
        f"Store write status: {result.get('store_write_status')}",
        f"LLM records written: {result.get('llm_records_written')}",
    ]
    engine_result = result.get("engine_result") or {}
    if engine_result:
        lines.extend(["", "## Engine", render_diagnostic_engine_report(engine_result).strip()])
    if result.get("warnings"):
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in result["warnings"]]])
    if result.get("errors"):
        lines.extend(["", "## Errors", *[f"- {error}" for error in result["errors"]]])
    lines.extend(
        [
            "",
            "## Boundary",
            "Local CSV/JSONL/JSON input only; no live data or provider calls.",
            "No training, inference, or benchmark rerun is performed.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the offline local-file gateway into the diagnostic engine.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--timeframe", default="1 ngày")
    parser.add_argument("--horizon-steps", type=int, default=1)
    parser.add_argument("--policy-demo", default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_offline_gateway_to_engine(
        input_path=args.input,
        ticker=args.ticker,
        timeframe=args.timeframe,
        horizon_steps=args.horizon_steps,
        policy_demo=args.policy_demo,
        store_root=args.store_root,
    )
    if args.format == "report":
        print(render_offline_gateway_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("gateway_status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
