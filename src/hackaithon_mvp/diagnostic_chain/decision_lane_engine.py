"""Layer 4: diagnostic decision lane assignment."""

from __future__ import annotations

from .chain_schema import (
    ALLOWED_DECISION_LANES,
    DecisionLaneOutput,
    NON_CLAIM_TEXT,
    assert_allowed,
    assert_no_forbidden_public_terms,
)


def run_decision_lane(quant_output: dict, scenario_output: dict, risk_output: dict) -> DecisionLaneOutput:
    signal = str(quant_output.get("quant_signal", "insufficient_evidence"))
    consensus = float(quant_output.get("consensus_strength", 0.0))
    scenario = str(scenario_output.get("scenario", "uncertain"))
    risk_level = str(risk_output.get("risk_level", "high"))
    risk_flags = set(risk_output.get("risk_flags", []))

    if signal == "exploratory_only" or "exploratory_only" in risk_flags:
        lane = "exploratory_only"
        reason = "The diagnostic remains exploratory under the static evidence boundary."
    elif signal == "insufficient_evidence" or "insufficient_data" in risk_flags:
        lane = "evidence_insufficient"
        reason = "Local sample evidence is insufficient for this diagnostic lane."
    elif risk_level in {"critical", "high"}:
        lane = "escalate_for_review"
        reason = "Risk governance requires human escalation."
    elif consensus < 0.02:
        lane = "reject_as_weak_evidence"
        reason = "Consensus strength is too weak for candidate routing."
    elif risk_level == "low" and scenario in {"growth", "correction"}:
        lane = "research_candidate"
        reason = "Static diagnostics support candidate review under human control."
    else:
        lane = "watchlist_review"
        reason = "Static diagnostics support watchlist review only."

    assert_allowed(lane, ALLOWED_DECISION_LANES, "decision_lane")
    output: DecisionLaneOutput = {
        "decision_lane": lane,
        "reason": reason,
        "human_review_required": True,
        "non_claim": NON_CLAIM_TEXT,
    }
    assert_no_forbidden_public_terms(output)
    return output
