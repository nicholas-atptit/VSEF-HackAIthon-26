"""Gateway-ready input payload contract for the local diagnostic engine core."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from typing import Any

from src.hackaithon_mvp.data_contracts import BarRecord
from src.hackaithon_mvp.forecast_actual_evaluation import (
    ALLOWED_FORECAST_DIAGNOSTICS,
    validate_forecast_actual_row,
)
from src.hackaithon_mvp.timeframe_schema import CANONICAL_TIMEFRAMES, normalize_timeframe


CLAIM_BOUNDARY = {
    "gateway_payload_contract_only": True,
    "provided_records_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Gateway-ready local input contract for research diagnostics; provided records only."
REQUIRED_TOP_LEVEL_SECTIONS = (
    "request",
    "market_bars",
    "forecast_rows",
    "model_diagnostics",
    "scenario_context",
    "risk_context",
    "social_context",
    "metadata",
)
REQUIRED_REQUEST_FIELDS = ("ticker", "timeframe", "horizon_steps")
FORECAST_REQUIRED_FIELDS = (
    "ticker",
    "timeframe",
    "prediction_timestamp",
    "horizon_steps",
    "forecast_diagnostic",
)
FORECAST_OPTIONAL_TEXT_FIELDS = (
    "engine_id",
    "model_key",
    "model_family",
    "route",
    "risk_level",
    "split_id",
    "source",
    "policy_id",
    "policy_name",
    "policy_runtime_status",
)
FORECAST_OPTIONAL_FLOAT_FIELDS = ("diagnostic_score", "confidence", "coverage_ratio")
MODEL_DIAGNOSTIC_REQUIRED_FIELDS = (
    "model_key",
    "model_family",
    "ticker",
    "timeframe",
    "horizon_steps",
    "forecast_diagnostic",
)
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
LIVE_DATA_KEYS = ("live_data", "is_live", "live_mode", "streaming_enabled")
ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
ACTION_LABEL_PATTERN = re.compile(r"\b(" + "|".join(re.escape(term) for term in ACTION_LABEL_TERMS) + r")\b", re.IGNORECASE)


def _safe_float(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number:
        raise ValueError(f"{field_name} must be numeric")
    return round(number, 6)


def _safe_int(value: Any, field_name: str) -> int:
    number = _safe_float(value, field_name)
    if int(number) != number:
        raise ValueError(f"{field_name} must be an integer")
    return int(number)


def _bounded_ratio(value: Any, field_name: str) -> float:
    number = _safe_float(value, field_name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return number


def _normalize_ticker(value: Any) -> str:
    ticker = str(value or "").strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    return ticker


def _walk_items(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}" if path else key_text
            yield next_path, key_text, nested
            yield from _walk_items(nested, next_path)
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            next_path = f"{path}[{index}]"
            yield from _walk_items(nested, next_path)


def _boundary_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, key, value in _walk_items(payload):
        lowered_key = key.lower()
        if any(token in lowered_key for token in SECRET_KEY_PATTERNS):
            errors.append(f"{path} must not include secret material")
        if lowered_key in LIVE_DATA_KEYS:
            errors.append(f"{path} must not include a live-data flag")
        if isinstance(value, str) and ACTION_LABEL_PATTERN.search(value):
            errors.append(f"{path} must not include action labels")
    return errors


def _normalize_market_bar(row: dict[str, Any]) -> dict[str, Any]:
    bar = BarRecord(
        ticker=_normalize_ticker(row.get("ticker")),
        timeframe=str(row.get("timeframe", "")),
        timestamp=row.get("timestamp"),
        open=row.get("open"),
        high=row.get("high"),
        low=row.get("low"),
        close=row.get("close"),
        volume=row.get("volume"),
        adjusted_close=row.get("adjusted_close"),
        source=row.get("source"),
        metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
    )
    output = {
        "ticker": bar.ticker,
        "timeframe": bar.timeframe,
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "adjusted_close": bar.adjusted_close,
        "source": bar.source,
        "metadata": bar.metadata,
    }
    return {key: value for key, value in output.items() if value is not None}


def _normalize_forecast_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in FORECAST_REQUIRED_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing required forecast fields: {missing}")
    forecast_diagnostic = str(row.get("forecast_diagnostic", "")).strip()
    if forecast_diagnostic not in ALLOWED_FORECAST_DIAGNOSTICS:
        raise ValueError(f"unsupported forecast_diagnostic: {forecast_diagnostic}")
    normalized = {
        "ticker": _normalize_ticker(row.get("ticker")),
        "timeframe": normalize_timeframe(str(row.get("timeframe", ""))),
        "prediction_timestamp": str(row.get("prediction_timestamp", "")).strip(),
        "horizon_steps": _safe_int(row.get("horizon_steps"), "horizon_steps"),
        "forecast_diagnostic": forecast_diagnostic,
    }
    if not normalized["prediction_timestamp"]:
        raise ValueError("prediction_timestamp must be non-empty")
    if normalized["horizon_steps"] <= 0:
        raise ValueError("horizon_steps must be positive")
    if "actual_future_return" in row or "actual_direction_label" in row:
        actual_row = validate_forecast_actual_row(row)
        normalized.update(actual_row)
    for field in FORECAST_OPTIONAL_TEXT_FIELDS:
        value = row.get(field)
        if value not in (None, ""):
            normalized[field] = str(value).strip()
    for field in FORECAST_OPTIONAL_FLOAT_FIELDS:
        value = row.get(field)
        if value not in (None, ""):
            normalized[field] = _bounded_ratio(value, field)
    return normalized


def _normalize_model_diagnostic(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in MODEL_DIAGNOSTIC_REQUIRED_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing required model diagnostic fields: {missing}")
    forecast_diagnostic = str(row.get("forecast_diagnostic", "")).strip()
    if forecast_diagnostic not in ALLOWED_FORECAST_DIAGNOSTICS:
        raise ValueError(f"unsupported forecast_diagnostic: {forecast_diagnostic}")
    normalized: dict[str, Any] = {
        "model_key": str(row.get("model_key", "")).strip(),
        "model_family": str(row.get("model_family", "")).strip(),
        "ticker": _normalize_ticker(row.get("ticker")),
        "timeframe": normalize_timeframe(str(row.get("timeframe", ""))),
        "horizon_steps": _safe_int(row.get("horizon_steps"), "horizon_steps"),
        "forecast_diagnostic": forecast_diagnostic,
    }
    if not normalized["model_key"]:
        raise ValueError("model_key must be non-empty")
    if not normalized["model_family"]:
        raise ValueError("model_family must be non-empty")
    if normalized["horizon_steps"] <= 0:
        raise ValueError("horizon_steps must be positive")
    for field in ("diagnostic_score", "confidence", "coverage_ratio"):
        value = row.get(field)
        if value not in (None, ""):
            normalized[field] = _bounded_ratio(value, field)
    for field in ("calibration_status", "policy_runtime_status", "engine_id", "source"):
        value = row.get(field)
        if value not in (None, ""):
            normalized[field] = str(value).strip()
    return normalized


def _normalize_sequence(value: Any, section: str, normalizer) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [f"{section} must be a list"]
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            errors.append(f"{section}[{index}] must be an object")
            continue
        try:
            normalized.append(normalizer(row))
        except (TypeError, ValueError) as exc:
            errors.append(f"{section}[{index}]: {exc}")
    return normalized, errors


def build_engine_input_contract() -> dict:
    """Return the canonical payload shape a later gateway must emit."""

    return {
        "contract_version": "1.0",
        "contract_status": "gateway_ready_local_contract",
        "required_sections": list(REQUIRED_TOP_LEVEL_SECTIONS),
        "request": {
            "required": list(REQUIRED_REQUEST_FIELDS),
            "optional": ["run_id", "policy_demo"],
            "ticker": "required uppercase-normalized identifier",
            "timeframe": {"canonical_values": list(CANONICAL_TIMEFRAMES)},
            "horizon_steps": "positive integer",
        },
        "sections": {
            "market_bars": "optional list of local OHLCV rows",
            "forecast_rows": "optional list of forecast diagnostic rows",
            "model_diagnostics": "optional list of baseline ML diagnostic rows",
            "scenario_context": "optional local diagnostic scenario context",
            "risk_context": "optional local diagnostic risk context",
            "social_context": "optional contract-only social context",
            "metadata": "optional local run metadata",
        },
        "allowed_forecast_diagnostics": sorted(ALLOWED_FORECAST_DIAGNOSTICS),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def normalize_engine_input_payload(payload: dict) -> dict:
    """Normalize a gateway-ready diagnostic payload or raise ``ValueError``."""

    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")
    payload_copy = deepcopy(payload)
    request = payload_copy.get("request")
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    missing = [field for field in REQUIRED_REQUEST_FIELDS if field not in request]
    if missing:
        raise ValueError(f"missing required request fields: {missing}")

    ticker = _normalize_ticker(request.get("ticker"))
    timeframe = normalize_timeframe(str(request.get("timeframe", "")))
    horizon_steps = _safe_int(request.get("horizon_steps"), "horizon_steps")
    if horizon_steps <= 0:
        raise ValueError("horizon_steps must be positive")

    normalized_request = {
        "ticker": ticker,
        "timeframe": timeframe,
        "horizon_steps": horizon_steps,
        "run_id": str(request.get("run_id") or f"engine-input-{ticker.lower()}-{timeframe}-h{horizon_steps}"),
        "policy_demo": request.get("policy_demo"),
    }

    market_bars, bar_errors = _normalize_sequence(payload_copy.get("market_bars", []), "market_bars", _normalize_market_bar)
    forecast_rows, forecast_errors = _normalize_sequence(
        payload_copy.get("forecast_rows", []),
        "forecast_rows",
        _normalize_forecast_row,
    )
    model_diagnostics, model_errors = _normalize_sequence(
        payload_copy.get("model_diagnostics", []),
        "model_diagnostics",
        _normalize_model_diagnostic,
    )
    errors = bar_errors + forecast_errors + model_errors + _boundary_errors(payload_copy)
    for section in ("scenario_context", "risk_context", "metadata"):
        if section in payload_copy and payload_copy[section] is not None and not isinstance(payload_copy[section], dict):
            errors.append(f"{section} must be an object")
    if (
        "social_context" in payload_copy
        and payload_copy["social_context"] is not None
        and not isinstance(payload_copy["social_context"], dict)
    ):
        errors.append("social_context must be an object when provided")
    if errors:
        raise ValueError("; ".join(errors))

    normalized = {
        "request": normalized_request,
        "market_bars": market_bars,
        "forecast_rows": forecast_rows,
        "model_diagnostics": model_diagnostics,
        "scenario_context": dict(payload_copy.get("scenario_context") or {}),
        "risk_context": dict(payload_copy.get("risk_context") or {}),
        "social_context": dict(payload_copy.get("social_context") or {}),
        "metadata": dict(payload_copy.get("metadata") or {}),
    }
    normalized["metadata"].setdefault("input_contract_version", "1.0")
    return normalized


def validate_engine_input_payload(payload: dict) -> dict:
    """Validate and normalize a diagnostic engine input payload."""

    errors: list[str] = []
    warnings: list[str] = []
    normalized_payload: dict[str, Any] | None = None
    try:
        normalized_payload = normalize_engine_input_payload(payload)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))

    if normalized_payload is not None:
        if not normalized_payload["market_bars"]:
            warnings.append("market_bars not provided")
        if not normalized_payload["forecast_rows"]:
            warnings.append("forecast_rows not provided")
        if not normalized_payload["model_diagnostics"]:
            warnings.append("model_diagnostics not provided")
        if not normalized_payload["social_context"]:
            warnings.append("social_context omitted; contract-only context remains empty")

    return {
        "is_valid": not errors,
        "normalized_payload": normalized_payload,
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_minimal_engine_input_fixture(
    *,
    ticker: str = "DEMO",
    timeframe: str = "1 ng\u00e0y",
    horizon_steps: int = 1,
) -> dict:
    """Build a tiny deterministic payload fixture for local engine checks."""

    ticker_value = _normalize_ticker(ticker)
    horizon_value = int(horizon_steps)
    timeframe_value = timeframe
    run_id = f"engine-input-{ticker_value.lower()}-h{horizon_value}"
    return {
        "request": {
            "ticker": ticker_value,
            "timeframe": timeframe_value,
            "horizon_steps": horizon_value,
            "run_id": run_id,
            "policy_demo": None,
        },
        "market_bars": [
            {
                "ticker": ticker_value,
                "timeframe": timeframe_value,
                "timestamp": "2026-06-19T00:00:00+07:00",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1000000,
            },
            {
                "ticker": ticker_value,
                "timeframe": timeframe_value,
                "timestamp": "2026-06-20T00:00:00+07:00",
                "open": 101.0,
                "high": 103.0,
                "low": 100.0,
                "close": 102.0,
                "volume": 1100000,
            },
        ],
        "forecast_rows": [
            {
                "ticker": ticker_value,
                "timeframe": timeframe_value,
                "prediction_timestamp": "2026-06-19T00:00:00+07:00",
                "horizon_steps": horizon_value,
                "forecast_diagnostic": "neutral_or_uncertain",
                "model_key": "logistic_l2",
                "model_family": "classification",
                "diagnostic_score": 0.58,
                "confidence": 0.72,
            }
        ],
        "model_diagnostics": [
            {
                "model_key": "logistic_l2",
                "model_family": "classification",
                "ticker": ticker_value,
                "timeframe": timeframe_value,
                "horizon_steps": horizon_value,
                "forecast_diagnostic": "neutral_or_uncertain",
                "diagnostic_score": 0.58,
                "confidence": 0.72,
                "coverage_ratio": 0.92,
                "calibration_status": "calibrated",
                "policy_runtime_status": "policy_not_applied",
            },
            {
                "model_key": "random_forest",
                "model_family": "classification",
                "ticker": ticker_value,
                "timeframe": timeframe_value,
                "horizon_steps": horizon_value,
                "forecast_diagnostic": "neutral_or_uncertain",
                "diagnostic_score": 0.56,
                "confidence": 0.7,
                "coverage_ratio": 0.9,
                "calibration_status": "calibrated",
                "policy_runtime_status": "policy_not_applied",
            },
            {
                "model_key": "arima_direction",
                "model_family": "statistical",
                "ticker": ticker_value,
                "timeframe": timeframe_value,
                "horizon_steps": horizon_value,
                "forecast_diagnostic": "neutral_or_uncertain",
                "diagnostic_score": 0.55,
                "confidence": 0.68,
                "coverage_ratio": 0.88,
                "calibration_status": "calibrated",
                "policy_runtime_status": "policy_not_applied",
            },
        ],
        "scenario_context": {
            "uncertainty_level": "low",
            "data_quality_status": "nominal",
            "evidence_status": "provided",
        },
        "risk_context": {
            "max_bar_age_days": 1,
            "manual_review_required": True,
        },
        "social_context": {
            "context_status": "not_ingested_contract_only",
            "records": [],
        },
        "metadata": {
            "fixture_id": run_id,
            "created_for": "gateway_ready_local_engine_core",
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect the diagnostic engine input contract.")
    parser.add_argument("--fixture", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    output = build_minimal_engine_input_fixture() if args.fixture else build_engine_input_contract()
    if args.fixture:
        output = validate_engine_input_payload(output)
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
