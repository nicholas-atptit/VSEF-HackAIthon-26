"""Risk Engine V3 with stronger local diagnostic data-quality checks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.hackaithon_mvp.engine_input_contract import (
    CLAIM_BOUNDARY as INPUT_CLAIM_BOUNDARY,
    build_minimal_engine_input_fixture,
    validate_engine_input_payload,
)
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.risk_engine_v2 import (
    evaluate_model_risk,
    evaluate_policy_risk,
    evaluate_scenario_risk,
)
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2


CLAIM_BOUNDARY = {
    **INPUT_CLAIM_BOUNDARY,
    "risk_assessment_only": True,
    "risk_engine_version": "v3",
}
NON_CLAIM_TEXT = "Risk Engine V3 diagnostic assessment over provided local records; human review required."
RISK_DIMENSIONS = (
    "ohlcv_integrity_risk",
    "liquidity_risk",
    "volatility_gap_risk",
    "manipulation_susceptibility_risk",
    "evidence_consistency_risk",
    "model_disagreement_risk",
    "calibration_risk",
    "policy_gate_risk",
    "scenario_stress_risk",
    "staleness_risk",
    "missing_context_risk",
)


def _level_from_score(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.67:
        return "high"
    if score >= 0.34:
        return "medium"
    return "low"


def _dimension(score: float, flags: list[str] | None = None, reason: str = "") -> dict:
    bounded = round(max(0.0, min(float(score), 1.0)), 6)
    return {
        "risk_level": _level_from_score(bounded),
        "score": bounded,
        "flags": list(dict.fromkeys(flags or [])),
        "reason": reason,
    }


def _validated_payload(payload: dict) -> tuple[dict, dict]:
    validation = validate_engine_input_payload(payload)
    normalized = validation["normalized_payload"] if validation["is_valid"] else {}
    return validation, normalized or {}


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _bars(payload: dict) -> tuple[dict, ...]:
    validation, normalized = _validated_payload(payload)
    if not validation["is_valid"]:
        return tuple()
    return tuple(normalized.get("market_bars", []) or ())


def build_risk_engine_v3_config() -> dict:
    """Build deterministic local thresholds for Risk Engine V3."""

    return {
        "config_version": "3.0",
        "risk_engine_version": "v3",
        "risk_dimensions": list(RISK_DIMENSIONS),
        "thresholds": {
            "critical_min": 0.9,
            "high_min": 0.67,
            "medium_min": 0.34,
            "near_zero_volume": 1.0,
            "extreme_range_ratio": 0.25,
            "large_gap_days": 3,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def evaluate_ohlcv_integrity_risk(payload: dict) -> dict:
    validation, normalized = _validated_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.95, ["invalid_payload"], "Payload failed canonical validation.")
    bars = normalized.get("market_bars", []) or []
    if not bars:
        return _dimension(0.8, ["missing_market_bars"], "No local OHLCV bars were provided.")
    flags: list[str] = []
    for index, bar in enumerate(bars):
        try:
            open_value = float(bar["open"])
            high_value = float(bar["high"])
            low_value = float(bar["low"])
            close_value = float(bar["close"])
            volume_value = float(bar["volume"])
        except (KeyError, TypeError, ValueError):
            flags.append(f"bar_{index}_non_numeric")
            continue
        if high_value < max(open_value, low_value, close_value):
            flags.append(f"bar_{index}_high_relation")
        if low_value > min(open_value, high_value, close_value):
            flags.append(f"bar_{index}_low_relation")
        if volume_value < 0:
            flags.append(f"bar_{index}_negative_volume")
    timestamps = [str(bar.get("timestamp", "")) for bar in bars]
    duplicate_count = sum(count - 1 for count in Counter(timestamps).values() if count > 1)
    if duplicate_count:
        flags.append("duplicate_timestamps")
    if flags:
        return _dimension(0.72 if "duplicate_timestamps" in flags else 0.9, flags, "OHLCV integrity issues require review.")
    return _dimension(0.1, [], "OHLCV integrity checks passed.")


def evaluate_liquidity_risk(payload: dict) -> dict:
    bars = _bars(payload)
    if not bars:
        return _dimension(0.75, ["missing_market_bars"], "Liquidity cannot be evaluated without local bars.")
    volumes = [float(bar.get("volume", 0.0) or 0.0) for bar in bars]
    near_zero = [volume for volume in volumes if volume <= 1.0]
    mean_volume = sum(volumes) / len(volumes) if volumes else 0.0
    flags: list[str] = []
    score = 0.1
    if near_zero:
        flags.append("near_zero_volume")
        score = max(score, 0.78)
    if mean_volume < 1_000:
        flags.append("very_low_mean_volume")
        score = max(score, 0.65)
    return _dimension(score, flags, "Liquidity risk was evaluated from local volume fields.")


def evaluate_volatility_gap_risk(payload: dict) -> dict:
    bars = _bars(payload)
    if not bars:
        return _dimension(0.65, ["missing_market_bars"], "Volatility and gap risk cannot be evaluated without bars.")
    flags: list[str] = []
    score = 0.1
    for index, bar in enumerate(bars):
        low_value = float(bar.get("low", 0.0) or 0.0)
        high_value = float(bar.get("high", 0.0) or 0.0)
        close_value = float(bar.get("close", 0.0) or 0.0)
        denominator = max(abs(close_value), 1.0)
        range_ratio = (high_value - low_value) / denominator
        if range_ratio >= 0.25:
            flags.append(f"bar_{index}_extreme_range")
            score = max(score, 0.75)
    parsed = sorted(value for value in (_parse_timestamp(bar.get("timestamp")) for bar in bars) if value is not None)
    gap_days = [
        (right - left).total_seconds() / 86400
        for left, right in zip(parsed, parsed[1:])
        if (right - left).total_seconds() / 86400 > 3
    ]
    if gap_days:
        flags.append("large_timestamp_gap")
        score = max(score, 0.7)
    return _dimension(score, flags, "Volatility range and timestamp gaps were evaluated locally.")


def evaluate_manipulation_susceptibility_risk(payload: dict) -> dict:
    bars = _bars(payload)
    if not bars:
        return _dimension(0.55, ["missing_market_bars"], "Manipulation susceptibility cannot be evaluated without bars.")
    signatures = [
        (
            round(float(bar.get("open", 0.0) or 0.0), 6),
            round(float(bar.get("high", 0.0) or 0.0), 6),
            round(float(bar.get("low", 0.0) or 0.0), 6),
            round(float(bar.get("close", 0.0) or 0.0), 6),
            round(float(bar.get("volume", 0.0) or 0.0), 6),
        )
        for bar in bars
    ]
    repeated = sum(count for count in Counter(signatures).values() if count > 1)
    flags: list[str] = []
    score = 0.1
    if repeated >= 2:
        flags.append("repeated_identical_ohlcv")
        score = 0.74
    if any(float(bar.get("volume", 0.0) or 0.0) == 0.0 for bar in bars):
        flags.append("zero_volume_bar")
        score = max(score, 0.68)
    return _dimension(score, flags, "Repeated identical OHLCV and zero-volume bars were checked.")


def evaluate_evidence_consistency_risk(
    *,
    payload: dict,
    ml_summary: dict | None = None,
    scenario_summary: dict | None = None,
) -> dict:
    validation, normalized = _validated_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.9, ["invalid_payload"], "Evidence consistency cannot be established for invalid payloads.")
    if (normalized.get("risk_context") or {}).get("force_critical_review") is True:
        return _dimension(0.95, ["critical_review_flag"], "Risk context requires critical review.")
    if ml_summary is None:
        ml_summary = run_ml_diagnostic_engine(tuple(normalized.get("model_diagnostics", []) or ()))
    if scenario_summary is None:
        scenario_summary = run_scenario_engine_v2(payload=normalized, ml_summary=ml_summary)
    flags: list[str] = []
    score = 0.1
    agreement = str((ml_summary or {}).get("agreement_status", "insufficient_models"))
    scenario_stability = str((scenario_summary or {}).get("stability_status", "uncertain"))
    scenario_risk = str((scenario_summary or {}).get("scenario_risk_level", "medium"))
    forecast_count = len(normalized.get("forecast_rows", []) or [])
    model_count = len(normalized.get("model_diagnostics", []) or [])
    if forecast_count == 0 and model_count == 0:
        flags.append("forecast_and_model_evidence_missing")
        score = max(score, 0.75)
    if agreement == "strong_agreement" and scenario_stability in {"unstable", "insufficient_evidence"}:
        flags.append("ml_scenario_consistency_conflict")
        score = max(score, 0.72)
    if agreement == "high_disagreement" and scenario_risk == "low":
        flags.append("model_disagreement_scenario_low_conflict")
        score = max(score, 0.68)
    if agreement in {"insufficient_models", "invalid_records"}:
        flags.append("ml_evidence_limited")
        score = max(score, 0.55)
    return _dimension(score, flags, "Consistency was checked across payload, ML summary, and scenario summary.")


def _evaluate_staleness_risk(payload: dict) -> dict:
    validation, normalized = _validated_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.55, ["staleness_not_evaluated"], "Staleness could not be evaluated.")
    bars = normalized.get("market_bars", []) or []
    risk_context = normalized.get("risk_context", {}) or {}
    value = risk_context.get("max_bar_age_days")
    parsed = [_parse_timestamp(bar.get("timestamp")) for bar in bars]
    parsed = [value for value in parsed if value is not None]
    if value in (None, "") and parsed:
        value = max(0, (datetime(2026, 6, 21, tzinfo=timezone.utc) - max(parsed).astimezone(timezone.utc)).days)
    if value in (None, ""):
        return _dimension(0.4, ["staleness_context_missing"], "Staleness context is missing.")
    try:
        days = float(value)
    except (TypeError, ValueError):
        return _dimension(0.55, ["staleness_context_invalid"], "Staleness context is invalid.")
    if days > 30:
        return _dimension(0.82, ["stale_local_rows"], "Provided local rows are stale for diagnostic review.")
    if days > 7:
        return _dimension(0.55, ["aging_local_rows"], "Provided local rows are aging and require reviewer attention.")
    return _dimension(0.1, [], "Staleness context is within local threshold.")


def _evaluate_missing_context_risk(payload: dict) -> dict:
    validation, normalized = _validated_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.55, ["context_invalid"], "Context could not be evaluated.")
    missing = [key for key in ("scenario_context", "risk_context") if not normalized.get(key)]
    if missing:
        return _dimension(0.45, [f"missing_{key}" for key in missing], "One or more optional contexts are absent.")
    return _dimension(0.1, [], "Required local diagnostic contexts are present.")


def run_risk_engine_v3(
    *,
    payload: dict,
    ml_summary: dict | None = None,
    scenario_summary: dict | None = None,
) -> dict:
    """Run Risk Engine V3 over the canonical local payload."""

    validation, normalized = _validated_payload(payload)
    if ml_summary is None:
        ml_summary = run_ml_diagnostic_engine(tuple(normalized.get("model_diagnostics", []) or ()))
    if scenario_summary is None:
        scenario_summary = run_scenario_engine_v2(payload=normalized or payload, ml_summary=ml_summary)
    model_risks = evaluate_model_risk(ml_summary or {})
    risk_dimensions = {
        "ohlcv_integrity_risk": evaluate_ohlcv_integrity_risk(payload),
        "liquidity_risk": evaluate_liquidity_risk(payload),
        "volatility_gap_risk": evaluate_volatility_gap_risk(payload),
        "manipulation_susceptibility_risk": evaluate_manipulation_susceptibility_risk(payload),
        "evidence_consistency_risk": evaluate_evidence_consistency_risk(
            payload=payload,
            ml_summary=ml_summary,
            scenario_summary=scenario_summary,
        ),
        "model_disagreement_risk": model_risks["model_disagreement_risk"],
        "calibration_risk": model_risks["calibration_risk"],
        "policy_gate_risk": evaluate_policy_risk(payload),
        "scenario_stress_risk": evaluate_scenario_risk(scenario_summary or {}),
        "staleness_risk": _evaluate_staleness_risk(payload),
        "missing_context_risk": _evaluate_missing_context_risk(payload),
    }
    scores = [float(value["score"]) for value in risk_dimensions.values()]
    risk_score = round(max(scores) if scores else 1.0, 6)
    risk_level = _level_from_score(risk_score)
    blocking_flags: list[str] = []
    if risk_level == "critical":
        blocking_flags.append("directional_diagnostic_blocked")
    for name, dimension in risk_dimensions.items():
        if dimension["risk_level"] in {"high", "critical"}:
            blocking_flags.extend(f"{name}:{flag}" for flag in dimension.get("flags", []) or [dimension["risk_level"]])
    risk_review_reason = (
        "Critical diagnostic risk blocks directional diagnostic output pending review."
        if risk_level == "critical"
        else "Risk Engine V3 dimensions remain under human review."
    )
    return {
        "risk_engine_status": "completed" if validation["is_valid"] else "completed_with_input_errors",
        "risk_engine_version": "v3",
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_dimensions": risk_dimensions,
        "blocking_flags": list(dict.fromkeys(blocking_flags)),
        "required_human_review": True,
        "human_review_required": True,
        "auto_execution_allowed": False,
        "risk_review_reason": risk_review_reason,
        "input_validation": validation,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _render_report(result: dict) -> str:
    lines = [
        "# Risk Engine V3",
        "",
        f"Status: {result.get('risk_engine_status')}",
        f"Version: {result.get('risk_engine_version')}",
        f"Risk level: {result.get('risk_level')}",
        f"Risk score: {result.get('risk_score')}",
        f"Blocking flags: {len(result.get('blocking_flags', []) or [])}",
        "Human review required: True",
        "Auto execution allowed: False",
        "",
        "Boundary: provided local records only; no live data, provider calls, training, inference, or benchmark rerun.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Risk Engine V3 on a deterministic local fixture.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    fixture = build_minimal_engine_input_fixture()
    ml_summary = run_ml_diagnostic_engine(tuple(fixture["model_diagnostics"]))
    scenario_summary = run_scenario_engine_v2(payload=fixture, ml_summary=ml_summary)
    result = run_risk_engine_v3(payload=fixture, ml_summary=ml_summary, scenario_summary=scenario_summary)
    if args.format == "report":
        print(_render_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
