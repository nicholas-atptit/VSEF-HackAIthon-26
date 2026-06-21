"""Baseline ML diagnostic summary layer over provided local records."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.forecast_actual_evaluation import ALLOWED_FORECAST_DIAGNOSTICS
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


CLAIM_BOUNDARY = {
    "baseline_ml_only": True,
    "provided_records_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Baseline ML-only diagnostic summary over provided records; human review required."
REQUIRED_FIELDS = (
    "model_key",
    "model_family",
    "ticker",
    "timeframe",
    "horizon_steps",
    "forecast_diagnostic",
)
OPTIONAL_RATIO_FIELDS = ("diagnostic_score", "confidence", "coverage_ratio")
ALLOWED_REVIEW_LANES = frozenset(
    {
        "standard_human_review",
        "evidence_insufficient_review",
        "policy_review_required",
        "risk_review_required",
        "calibration_review_required",
    }
)
NON_DIRECTIONAL_DIAGNOSTICS = frozenset(
    {"neutral_or_uncertain", "insufficient_evidence", "exploratory_only"}
)


def _safe_int(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    return number


def _safe_ratio(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return round(number, 6)


def _normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing required ML diagnostic fields: {missing}")
    diagnostic = str(row.get("forecast_diagnostic", "")).strip()
    if diagnostic not in ALLOWED_FORECAST_DIAGNOSTICS:
        raise ValueError(f"unsupported forecast_diagnostic: {diagnostic}")
    ticker = str(row.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError("ticker must be non-empty")
    horizon_steps = _safe_int(row.get("horizon_steps"), "horizon_steps")
    if horizon_steps <= 0:
        raise ValueError("horizon_steps must be positive")
    normalized: dict[str, Any] = {
        "model_key": str(row.get("model_key", "")).strip(),
        "model_family": str(row.get("model_family", "")).strip(),
        "ticker": ticker,
        "timeframe": normalize_timeframe(str(row.get("timeframe", ""))),
        "horizon_steps": horizon_steps,
        "forecast_diagnostic": diagnostic,
    }
    if not normalized["model_key"]:
        raise ValueError("model_key must be non-empty")
    if not normalized["model_family"]:
        raise ValueError("model_family must be non-empty")
    for field in OPTIONAL_RATIO_FIELDS:
        value = row.get(field)
        if value not in (None, ""):
            normalized[field] = _safe_ratio(value, field)
    for field in ("calibration_status", "policy_runtime_status", "engine_id", "source"):
        value = row.get(field)
        if value not in (None, ""):
            normalized[field] = str(value).strip()
    return normalized


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _empty_output(status: str, errors: list[str] | None = None) -> dict:
    return {
        "ml_engine_status": status,
        "model_count": 0,
        "family_count": 0,
        "diagnostic_distribution": {},
        "agreement_status": "insufficient_models",
        "signal_quality": {
            "quality_status": "insufficient",
            "mean_confidence": None,
            "mean_diagnostic_score": None,
            "mean_coverage_ratio": None,
            "insufficient_evidence_count": 0,
        },
        "coverage_status": "missing",
        "calibration_status": "missing",
        "recommended_review_lane": "evidence_insufficient_review",
        "validation": {
            "is_valid": not errors,
            "errors": errors or [],
            "warnings": ["no ML diagnostic records provided"] if not errors else [],
        },
        "human_review_required": True,
        "auto_execution_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def validate_ml_diagnostic_records(records: tuple[dict, ...]) -> dict:
    """Validate provided ML diagnostic records without running model logic."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(records, tuple):
        errors.append("records must be a tuple")
        records = tuple(records or ()) if isinstance(records, list) else ()
    normalized_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue
        try:
            normalized_records.append(_normalize_record(record))
        except (TypeError, ValueError) as exc:
            errors.append(f"records[{index}]: {exc}")
    if not normalized_records:
        warnings.append("no valid ML diagnostic records provided")
    return {
        "is_valid": not errors,
        "normalized_records": tuple(normalized_records),
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def summarize_ml_diagnostics(records: tuple[dict, ...]) -> dict:
    """Summarize model families and forecast diagnostic labels."""

    validation = validate_ml_diagnostic_records(records)
    normalized = tuple(validation["normalized_records"])
    if not validation["is_valid"]:
        return _empty_output("validation_failed", list(validation["errors"]))
    if not normalized:
        return _empty_output("insufficient_records")
    diagnostics = Counter(str(row["forecast_diagnostic"]) for row in normalized)
    families = Counter(str(row["model_family"]) for row in normalized)
    return {
        "ml_engine_status": "completed",
        "model_count": len(normalized),
        "family_count": len(families),
        "diagnostic_distribution": dict(sorted(diagnostics.items())),
        "family_distribution": dict(sorted(families.items())),
        "validation": validation,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def compute_model_agreement(records: tuple[dict, ...]) -> dict:
    """Compute agreement across provided diagnostic labels."""

    validation = validate_ml_diagnostic_records(records)
    normalized = tuple(validation["normalized_records"])
    if not validation["is_valid"]:
        return {
            "agreement_status": "invalid_records",
            "agreement_ratio": 0.0,
            "top_diagnostic": None,
            "conflicting_directional_count": 0,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
    if len(normalized) < 2:
        return {
            "agreement_status": "insufficient_models",
            "agreement_ratio": 1.0 if normalized else 0.0,
            "top_diagnostic": normalized[0]["forecast_diagnostic"] if normalized else None,
            "conflicting_directional_count": 0,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    counts = Counter(str(row["forecast_diagnostic"]) for row in normalized)
    top_diagnostic, top_count = counts.most_common(1)[0]
    agreement_ratio = round(top_count / len(normalized), 6)
    has_positive = counts.get("positive_bias", 0) > 0
    has_negative = counts.get("negative_bias", 0) > 0
    conflicting_directional_count = counts.get("positive_bias", 0) + counts.get("negative_bias", 0) if has_positive and has_negative else 0
    if conflicting_directional_count:
        agreement_status = "high_disagreement"
    elif agreement_ratio >= 0.8:
        agreement_status = "strong_agreement"
    elif agreement_ratio >= 0.6:
        agreement_status = "partial_agreement"
    else:
        agreement_status = "mixed_diagnostics"
    return {
        "agreement_status": agreement_status,
        "agreement_ratio": agreement_ratio,
        "top_diagnostic": top_diagnostic,
        "conflicting_directional_count": conflicting_directional_count,
        "diagnostic_distribution": dict(sorted(counts.items())),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def compute_signal_quality(records: tuple[dict, ...]) -> dict:
    """Compute deterministic evidence-quality status for provided records."""

    validation = validate_ml_diagnostic_records(records)
    normalized = tuple(validation["normalized_records"])
    if not validation["is_valid"] or not normalized:
        return {
            "quality_status": "insufficient",
            "mean_confidence": None,
            "mean_diagnostic_score": None,
            "mean_coverage_ratio": None,
            "coverage_status": "missing",
            "calibration_status": "missing",
            "insufficient_evidence_count": 0,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
    mean_confidence = _mean([float(row["confidence"]) for row in normalized if "confidence" in row])
    mean_score = _mean([float(row["diagnostic_score"]) for row in normalized if "diagnostic_score" in row])
    mean_coverage = _mean([float(row["coverage_ratio"]) for row in normalized if "coverage_ratio" in row])
    insufficient_count = sum(1 for row in normalized if row["forecast_diagnostic"] == "insufficient_evidence")

    if mean_coverage is None:
        coverage_status = "missing"
    elif mean_coverage >= 0.75:
        coverage_status = "strong"
    elif mean_coverage >= 0.45:
        coverage_status = "partial"
    else:
        coverage_status = "weak"

    calibration_values = [str(row.get("calibration_status", "")).strip() for row in normalized if row.get("calibration_status")]
    if not calibration_values:
        calibration_status = "missing"
    elif any(value in {"weak_calibration", "uncalibrated", "calibration_review_required"} for value in calibration_values):
        calibration_status = "weak"
    elif len(set(calibration_values)) > 1:
        calibration_status = "mixed"
    else:
        calibration_status = calibration_values[0]

    if insufficient_count == len(normalized):
        quality_status = "insufficient"
    elif coverage_status in {"missing", "weak"} or (mean_confidence is not None and mean_confidence < 0.45):
        quality_status = "weak"
    elif mean_confidence is not None and mean_confidence >= 0.65 and coverage_status == "strong":
        quality_status = "strong"
    else:
        quality_status = "adequate"
    return {
        "quality_status": quality_status,
        "mean_confidence": mean_confidence,
        "mean_diagnostic_score": mean_score,
        "mean_coverage_ratio": mean_coverage,
        "coverage_status": coverage_status,
        "calibration_status": calibration_status,
        "insufficient_evidence_count": insufficient_count,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _recommended_review_lane(agreement: dict, quality: dict, records: tuple[dict, ...]) -> str:
    policy_statuses = {str(row.get("policy_runtime_status", "")).strip() for row in records if row.get("policy_runtime_status")}
    if any(status in {"policy_review_required", "policy_invalid"} for status in policy_statuses):
        return "policy_review_required"
    if quality.get("calibration_status") in {"weak", "uncalibrated", "calibration_review_required"}:
        return "calibration_review_required"
    if agreement.get("agreement_status") == "high_disagreement":
        return "risk_review_required"
    if quality.get("quality_status") in {"insufficient", "weak"}:
        return "evidence_insufficient_review"
    return "standard_human_review"


def run_ml_diagnostic_engine(records: tuple[dict, ...]) -> dict:
    """Run the baseline ML diagnostic layer over provided records only."""

    validation = validate_ml_diagnostic_records(records)
    normalized = tuple(validation["normalized_records"])
    if not validation["is_valid"]:
        return _empty_output("validation_failed", list(validation["errors"]))
    if not normalized:
        return _empty_output("insufficient_records")
    summary = summarize_ml_diagnostics(normalized)
    agreement = compute_model_agreement(normalized)
    quality = compute_signal_quality(normalized)
    lane = _recommended_review_lane(agreement, quality, normalized)
    if lane not in ALLOWED_REVIEW_LANES:
        raise ValueError(f"unsupported review lane: {lane}")
    return {
        "ml_engine_status": "completed",
        "model_count": summary["model_count"],
        "family_count": summary["family_count"],
        "diagnostic_distribution": summary["diagnostic_distribution"],
        "agreement_status": agreement["agreement_status"],
        "agreement": agreement,
        "signal_quality": quality,
        "coverage_status": quality["coverage_status"],
        "calibration_status": quality["calibration_status"],
        "recommended_review_lane": lane,
        "validation": validation,
        "human_review_required": True,
        "auto_execution_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the baseline ML diagnostic engine on a local fixture.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _render_report(result: dict) -> str:
    lines = [
        "# ML Diagnostic Engine",
        "",
        f"Status: {result.get('ml_engine_status')}",
        f"Models: {result.get('model_count')}",
        f"Families: {result.get('family_count')}",
        f"Agreement: {result.get('agreement_status')}",
        f"Signal quality: {result.get('signal_quality', {}).get('quality_status')}",
        f"Review lane: {result.get('recommended_review_lane')}",
        "Human review required: True",
        "Auto execution allowed: False",
        "",
        "Boundary: provided records only; no live data, provider calls, training, inference, or benchmark rerun.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    fixture = build_minimal_engine_input_fixture()
    result = run_ml_diagnostic_engine(tuple(fixture["model_diagnostics"]))
    if args.format == "report":
        print(_render_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
