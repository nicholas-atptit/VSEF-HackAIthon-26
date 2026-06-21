"""Local Scenario Engine V2 for diagnostic stability checks."""

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
    "scenario_stress_context_only": True,
}
NON_CLAIM_TEXT = "Local scenario diagnostics only; scenario contexts are not market forecasts."
SCENARIO_IDS = (
    "base_case",
    "missing_evidence_case",
    "high_uncertainty_case",
    "model_disagreement_case",
    "calibration_stress_case",
    "data_quality_stress_case",
)


def build_scenario_registry_v2() -> tuple[dict, ...]:
    """Build the fixed local Scenario Engine V2 registry."""

    descriptions = {
        "base_case": "Provided records pass the base local diagnostic context.",
        "missing_evidence_case": "Provided records are missing or too sparse.",
        "high_uncertainty_case": "Local context marks uncertainty as high.",
        "model_disagreement_case": "Provided model diagnostics conflict or remain mixed.",
        "calibration_stress_case": "Calibration context requires reviewer attention.",
        "data_quality_stress_case": "Local data quality context is degraded.",
    }
    return tuple(
        {
            "scenario_id": scenario_id,
            "scenario_type": "diagnostic_stress_context",
            "description": descriptions[scenario_id],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
        for scenario_id in SCENARIO_IDS
    )


def validate_scenario_context(context: dict) -> dict:
    """Validate optional scenario context without external lookups."""

    errors: list[str] = []
    warnings: list[str] = []
    if context is None:
        context = {}
    if not isinstance(context, dict):
        return {
            "is_valid": False,
            "normalized_context": {},
            "errors": ["scenario context must be an object"],
            "warnings": [],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
    lowered_keys = {str(key).lower() for key in context}
    if any(key in lowered_keys for key in {"live_data", "provider_feed", "provider_api"}):
        errors.append("scenario context must not include live or provider fields")
    uncertainty = str(context.get("uncertainty_level", "low")).strip().lower()
    data_quality = str(context.get("data_quality_status", "nominal")).strip().lower()
    evidence_status = str(context.get("evidence_status", "provided")).strip().lower()
    disagreement = str(context.get("model_disagreement_level", "low")).strip().lower()
    allowed = {
        "uncertainty_level": {"low", "medium", "high"},
        "data_quality_status": {"nominal", "degraded", "missing"},
        "evidence_status": {"provided", "partial", "missing"},
        "model_disagreement_level": {"low", "medium", "high"},
    }
    values = {
        "uncertainty_level": uncertainty,
        "data_quality_status": data_quality,
        "evidence_status": evidence_status,
        "model_disagreement_level": disagreement,
    }
    for key, value in values.items():
        if value not in allowed[key]:
            errors.append(f"{key} is not allowed: {value}")
    if not context:
        warnings.append("scenario context omitted; base context assumed")
    normalized = {
        "uncertainty_level": uncertainty if uncertainty in allowed["uncertainty_level"] else "high",
        "data_quality_status": data_quality if data_quality in allowed["data_quality_status"] else "missing",
        "evidence_status": evidence_status if evidence_status in allowed["evidence_status"] else "missing",
        "model_disagreement_level": disagreement if disagreement in allowed["model_disagreement_level"] else "high",
        "calibration_stress": bool(context.get("calibration_stress", False)),
    }
    return {
        "is_valid": not errors,
        "normalized_context": normalized,
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _risk_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(level, 1)


def _scenario_result(scenario_id: str, triggered: bool, risk_level: str, note: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "triggered": bool(triggered),
        "risk_level": risk_level,
        "diagnostic_note": note,
    }


def run_scenario_engine_v2(
    *,
    payload: dict,
    ml_summary: dict | None = None,
) -> dict:
    """Run local diagnostic scenario contexts over the provided payload."""

    payload_validation = validate_engine_input_payload(payload)
    normalized_payload = payload_validation.get("normalized_payload") or {}
    context_validation = validate_scenario_context(normalized_payload.get("scenario_context", {}))
    context = context_validation["normalized_context"]
    if ml_summary is None:
        ml_summary = run_ml_diagnostic_engine(tuple(normalized_payload.get("model_diagnostics", []) or ()))

    model_count = int((ml_summary or {}).get("model_count", 0) or 0)
    agreement = str((ml_summary or {}).get("agreement_status", "insufficient_models"))
    calibration = str((ml_summary or {}).get("calibration_status", "missing"))
    evidence_missing = (
        not payload_validation.get("is_valid", False)
        or model_count == 0
        or context.get("evidence_status") == "missing"
        or str((ml_summary or {}).get("ml_engine_status")) in {"insufficient_records", "validation_failed"}
    )
    high_uncertainty = context.get("uncertainty_level") == "high"
    disagreement = agreement in {"high_disagreement", "mixed_diagnostics"} or context.get("model_disagreement_level") == "high"
    calibration_stress = context.get("calibration_stress") is True or calibration in {"weak", "uncalibrated", "missing"}
    data_quality_stress = context.get("data_quality_status") in {"degraded", "missing"}

    scenario_results = [
        _scenario_result("base_case", not any((evidence_missing, high_uncertainty, disagreement, calibration_stress, data_quality_stress)), "low", "Base local diagnostic context."),
        _scenario_result("missing_evidence_case", evidence_missing, "high", "Evidence is missing or insufficient."),
        _scenario_result("high_uncertainty_case", high_uncertainty, "medium", "Uncertainty context is high."),
        _scenario_result("model_disagreement_case", disagreement, "high", "Model diagnostics are in disagreement."),
        _scenario_result("calibration_stress_case", calibration_stress, "medium", "Calibration context requires review."),
        _scenario_result("data_quality_stress_case", data_quality_stress, "high", "Data quality context is stressed."),
    ]
    triggered = [row for row in scenario_results if row["triggered"] and row["scenario_id"] != "base_case"]
    if not triggered:
        dominant = "base_case"
        risk_level = "low"
        stability = "stable"
    else:
        dominant_row = sorted(triggered, key=lambda row: _risk_rank(row["risk_level"]), reverse=True)[0]
        dominant = dominant_row["scenario_id"]
        risk_level = dominant_row["risk_level"]
        if dominant == "missing_evidence_case":
            stability = "insufficient_evidence"
        elif risk_level == "high":
            stability = "unstable"
        else:
            stability = "uncertain"
    return {
        "scenario_engine_status": "completed" if payload_validation["is_valid"] and context_validation["is_valid"] else "completed_with_warnings",
        "scenario_count": len(scenario_results),
        "scenario_results": scenario_results,
        "dominant_scenario": dominant,
        "scenario_risk_level": risk_level,
        "stability_status": stability,
        "required_human_review": True,
        "human_review_required": True,
        "auto_execution_allowed": False,
        "payload_validation": payload_validation,
        "context_validation": context_validation,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Scenario Engine V2 on a deterministic local fixture.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _render_report(result: dict) -> str:
    lines = [
        "# Scenario Engine V2",
        "",
        f"Status: {result.get('scenario_engine_status')}",
        f"Scenarios: {result.get('scenario_count')}",
        f"Dominant scenario: {result.get('dominant_scenario')}",
        f"Scenario risk level: {result.get('scenario_risk_level')}",
        f"Stability: {result.get('stability_status')}",
        "Human review required: True",
        "Auto execution allowed: False",
        "",
        "Boundary: local scenario context only; no live data, provider calls, training, inference, or benchmark rerun.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    fixture = build_minimal_engine_input_fixture()
    ml_summary = run_ml_diagnostic_engine(tuple(fixture["model_diagnostics"]))
    result = run_scenario_engine_v2(payload=fixture, ml_summary=ml_summary)
    if args.format == "report":
        print(_render_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
