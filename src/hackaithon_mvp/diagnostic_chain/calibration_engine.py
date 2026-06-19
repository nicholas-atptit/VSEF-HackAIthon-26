"""Layer 6: static confidence calibration without model updates."""

from __future__ import annotations

from .chain_schema import CalibrationOutput, assert_no_forbidden_public_terms

RISK_FACTORS = {"low": 1.0, "medium": 0.75, "high": 0.4, "critical": 0.1}
LANE_FACTORS = {
    "research_candidate": 1.0,
    "watchlist_review": 0.8,
    "reject_as_weak_evidence": 0.35,
    "escalate_for_review": 0.3,
    "evidence_insufficient": 0.2,
    "exploratory_only": 0.25,
}


def run_calibration(
    quant_output: dict,
    scenario_output: dict,
    risk_output: dict,
    decision_output: dict,
) -> CalibrationOutput:
    scenario_confidence = float(scenario_output.get("scenario_confidence", 0.0))
    consensus = float(quant_output.get("consensus_strength", 0.0))
    risk_factor = RISK_FACTORS.get(str(risk_output.get("risk_level", "high")), 0.4)
    lane_factor = LANE_FACTORS.get(str(decision_output.get("decision_lane", "evidence_insufficient")), 0.2)
    calibrated = max(0.0, min(1.0, ((scenario_confidence + consensus) / 2.0) * risk_factor * lane_factor))

    output: CalibrationOutput = {
        "calibrated_confidence": round(calibrated, 6),
        "calibration_policy": "static_confidence_adjustment_only",
        "fine_tuning_performed": False,
        "explanation": "No model tuning, retraining, or hyperparameter search was performed.",
    }
    assert_no_forbidden_public_terms(output)
    return output
