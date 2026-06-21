"""Gateway-ready diagnostic risk engine over provided local payloads."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.engine_input_contract import (
    CLAIM_BOUNDARY as INPUT_CLAIM_BOUNDARY,
    build_minimal_engine_input_fixture,
    validate_engine_input_payload,
)
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine


CLAIM_BOUNDARY = {
    **INPUT_CLAIM_BOUNDARY,
    "risk_assessment_only": True,
}
NON_CLAIM_TEXT = "Diagnostic risk assessment over provided local records; human review required."
RISK_LEVELS = ("low", "medium", "high", "critical")


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


def build_risk_engine_v2_config() -> dict:
    """Build deterministic local thresholds for Risk Engine V2."""

    return {
        "config_version": "2.0",
        "risk_levels": list(RISK_LEVELS),
        "thresholds": {
            "low_max": 0.33,
            "medium_max": 0.66,
            "high_max": 0.89,
            "critical_min": 0.9,
        },
        "risk_dimensions": [
            "data_quality_risk",
            "evidence_coverage_risk",
            "model_disagreement_risk",
            "calibration_risk",
            "policy_gate_risk",
            "scenario_stress_risk",
            "staleness_risk",
            "missing_context_risk",
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def evaluate_data_quality_risk(payload: dict) -> dict:
    validation = validate_engine_input_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.95, ["invalid_input_payload"], "Input payload failed contract validation.")
    normalized = validation["normalized_payload"] or {}
    bars = normalized.get("market_bars", [])
    risk_context = normalized.get("risk_context", {})
    if risk_context.get("force_critical_review") is True:
        return _dimension(0.95, ["critical_review_flag"], "Risk context requires critical review.")
    if not bars:
        return _dimension(0.75, ["missing_market_bars"], "No local OHLCV rows were provided.")
    if len(bars) < 2:
        return _dimension(0.45, ["limited_market_bars"], "Only one local OHLCV row was provided.")
    return _dimension(0.1, [], "Local OHLCV rows passed contract validation.")


def evaluate_evidence_risk(payload: dict) -> dict:
    validation = validate_engine_input_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.9, ["invalid_evidence_payload"], "Evidence inputs failed contract validation.")
    normalized = validation["normalized_payload"] or {}
    model_count = len(normalized.get("model_diagnostics", []) or [])
    forecast_count = len(normalized.get("forecast_rows", []) or [])
    bar_count = len(normalized.get("market_bars", []) or [])
    flags: list[str] = []
    score = 0.1
    if model_count == 0:
        flags.append("missing_model_diagnostics")
        score = max(score, 0.75)
    elif model_count < 2:
        flags.append("limited_model_diagnostics")
        score = max(score, 0.45)
    if forecast_count == 0:
        flags.append("missing_forecast_rows")
        score = max(score, 0.55)
    if bar_count == 0:
        flags.append("missing_market_bars")
        score = max(score, 0.7)
    reason = "Evidence coverage is sufficient for local diagnostic review." if not flags else "Evidence coverage is limited."
    return _dimension(score, flags, reason)


def evaluate_model_risk(ml_summary: dict) -> dict:
    status = str((ml_summary or {}).get("ml_engine_status", "insufficient_records"))
    agreement = str((ml_summary or {}).get("agreement_status", "insufficient_models"))
    calibration = str((ml_summary or {}).get("calibration_status", "missing"))
    flags: list[str] = []
    disagreement_score = 0.1
    calibration_score = 0.1
    if status in {"validation_failed", "insufficient_records"}:
        flags.append("ml_records_insufficient")
        disagreement_score = max(disagreement_score, 0.7)
    if agreement == "high_disagreement":
        flags.append("model_diagnostic_conflict")
        disagreement_score = max(disagreement_score, 0.8)
    elif agreement in {"mixed_diagnostics", "invalid_records"}:
        flags.append("model_diagnostics_mixed")
        disagreement_score = max(disagreement_score, 0.55)
    elif agreement == "partial_agreement":
        disagreement_score = max(disagreement_score, 0.35)
    if calibration in {"weak", "uncalibrated", "calibration_review_required"}:
        flags.append("weak_calibration")
        calibration_score = max(calibration_score, 0.65)
    elif calibration in {"missing", "mixed"}:
        flags.append("calibration_context_limited")
        calibration_score = max(calibration_score, 0.4)
    return {
        "model_disagreement_risk": _dimension(
            disagreement_score,
            [flag for flag in flags if "model" in flag or "ml_" in flag],
            "Model diagnostic agreement was evaluated from provided records.",
        ),
        "calibration_risk": _dimension(
            calibration_score,
            [flag for flag in flags if "calibration" in flag],
            "Calibration status was evaluated from provided records.",
        ),
    }


def evaluate_policy_risk(payload: dict) -> dict:
    validation = validate_engine_input_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.65, ["policy_context_invalid"], "Policy context could not be evaluated.")
    normalized = validation["normalized_payload"] or {}
    statuses = {
        str(row.get("policy_runtime_status", "")).strip()
        for row in normalized.get("model_diagnostics", [])
        if row.get("policy_runtime_status")
    }
    policy_demo = normalized.get("request", {}).get("policy_demo")
    if any(status in {"policy_review_required", "policy_invalid"} for status in statuses):
        return _dimension(0.75, ["policy_review_needed"], "Policy runtime status requires review.")
    if any(status in {"downgraded_to_uncertain", "non_directional_preserved"} for status in statuses) or policy_demo:
        return _dimension(0.25, ["policy_gate_tracked"], "Policy gate state was tracked without failure.")
    return _dimension(0.1, [], "No policy gate risk was detected.")


def evaluate_scenario_risk(scenario_summary: dict) -> dict:
    if not scenario_summary:
        return _dimension(0.45, ["scenario_context_missing"], "Scenario summary was not provided.")
    risk_level = str(scenario_summary.get("scenario_risk_level", "medium"))
    stability = str(scenario_summary.get("stability_status") or ("stable" if risk_level == "low" else "uncertain"))
    score_by_level = {"low": 0.1, "medium": 0.45, "high": 0.72, "critical": 0.92}
    score = score_by_level.get(risk_level, 0.45)
    flags: list[str] = []
    if stability in {"unstable", "insufficient_evidence", "uncertain"}:
        flags.append(f"scenario_{stability}")
        score = max(score, 0.55)
    return _dimension(score, flags, "Scenario stress context was evaluated locally.")


def _evaluate_staleness_risk(payload: dict) -> dict:
    validation = validate_engine_input_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.5, ["staleness_not_evaluated"], "Staleness could not be evaluated.")
    normalized = validation["normalized_payload"] or {}
    risk_context = normalized.get("risk_context", {})
    value = risk_context.get("max_bar_age_days")
    if value in (None, ""):
        return _dimension(0.35, ["staleness_context_missing"], "Staleness context was not provided.")
    try:
        days = float(value)
    except (TypeError, ValueError):
        return _dimension(0.55, ["staleness_context_invalid"], "Staleness context is invalid.")
    if days > 10:
        return _dimension(0.75, ["stale_local_rows"], "Provided local rows are stale for this diagnostic run.")
    if days > 3:
        return _dimension(0.45, ["aging_local_rows"], "Provided local rows require reviewer attention.")
    return _dimension(0.1, [], "Staleness context is within the local threshold.")


def _evaluate_missing_context_risk(payload: dict) -> dict:
    validation = validate_engine_input_payload(payload)
    if not validation["is_valid"]:
        return _dimension(0.55, ["context_invalid"], "Context could not be evaluated.")
    normalized = validation["normalized_payload"] or {}
    missing = [
        key
        for key in ("scenario_context", "risk_context")
        if not normalized.get(key)
    ]
    if missing:
        return _dimension(0.45, [f"missing_{key}" for key in missing], "One or more optional contexts are absent.")
    return _dimension(0.1, [], "Required local diagnostic contexts are present.")


def run_risk_engine_v2(
    *,
    payload: dict,
    ml_summary: dict | None = None,
    scenario_summary: dict | None = None,
) -> dict:
    """Run Risk Engine V2 over a normalized or raw gateway-ready payload."""

    normalized_result = validate_engine_input_payload(payload)
    normalized_payload = normalized_result["normalized_payload"] if normalized_result["is_valid"] else payload
    if ml_summary is None:
        records = tuple((normalized_payload or {}).get("model_diagnostics", []) or ())
        ml_summary = run_ml_diagnostic_engine(records)

    model_risks = evaluate_model_risk(ml_summary or {})
    risk_dimensions = {
        "data_quality_risk": evaluate_data_quality_risk(payload),
        "evidence_coverage_risk": evaluate_evidence_risk(payload),
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
        "Critical diagnostic risk requires review before directional diagnostic output."
        if risk_level == "critical"
        else "Risk dimensions remain under reviewer control."
    )
    return {
        "risk_engine_status": "completed" if normalized_result["is_valid"] else "completed_with_input_errors",
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_dimensions": risk_dimensions,
        "blocking_flags": list(dict.fromkeys(blocking_flags)),
        "required_human_review": True,
        "human_review_required": True,
        "auto_execution_allowed": False,
        "risk_review_reason": risk_review_reason,
        "input_validation": normalized_result,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Risk Engine V2 on a deterministic local fixture.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _render_report(result: dict) -> str:
    lines = [
        "# Risk Engine V2",
        "",
        f"Status: {result.get('risk_engine_status')}",
        f"Risk level: {result.get('risk_level')}",
        f"Risk score: {result.get('risk_score')}",
        f"Blocking flags: {len(result.get('blocking_flags', []) or [])}",
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
    ml_summary = run_ml_diagnostic_engine(tuple(fixture["model_diagnostics"]))
    result = run_risk_engine_v2(payload=fixture, ml_summary=ml_summary, scenario_summary={"scenario_risk_level": "low"})
    if args.format == "report":
        print(_render_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
