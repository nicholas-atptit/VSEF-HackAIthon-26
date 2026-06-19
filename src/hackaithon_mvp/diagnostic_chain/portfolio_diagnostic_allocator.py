"""Layer 7: hypothetical research sizing view for reviewer workflow."""

from __future__ import annotations

from .chain_schema import (
    ALLOWED_ALLOCATION_VIEWS,
    NON_CLAIM_TEXT,
    PortfolioDiagnosticAllocatorOutput,
    assert_allowed,
    assert_no_forbidden_public_terms,
)


def run_portfolio_diagnostic_allocator(
    decision_output: dict,
    risk_output: dict,
    calibration_output: dict,
) -> PortfolioDiagnosticAllocatorOutput:
    lane = str(decision_output.get("decision_lane", "evidence_insufficient"))
    risk_level = str(risk_output.get("risk_level", "high"))
    calibrated_confidence = float(calibration_output.get("calibrated_confidence", 0.0))

    if lane == "evidence_insufficient":
        view = "insufficient_evidence"
        max_weight = 0.0
        explanation = "Static evidence is insufficient for a research sizing view."
    elif risk_level in {"high", "critical"}:
        view = "no_allocation"
        max_weight = 0.0
        explanation = "Risk governance blocks a research sizing candidate."
    elif risk_level == "medium":
        view = "risk_capped_candidate"
        max_weight = min(0.02, calibrated_confidence * 0.05)
        explanation = "Medium risk limits this to a capped research sizing view."
    elif lane == "research_candidate":
        view = "research_weight_candidate"
        max_weight = min(0.05, calibrated_confidence * 0.1)
        explanation = "Low risk and candidate lane allow a bounded research sizing view."
    else:
        view = "no_allocation"
        max_weight = 0.0
        explanation = "Decision lane does not support a research sizing candidate."

    assert_allowed(view, ALLOWED_ALLOCATION_VIEWS, "allocation_view")
    output: PortfolioDiagnosticAllocatorOutput = {
        "allocation_view": view,
        "max_research_weight": round(max_weight, 6),
        "allocation_is_advisory": False,
        "explanation": explanation,
        "non_claim": NON_CLAIM_TEXT,
    }
    assert_no_forbidden_public_terms(output)
    return output
