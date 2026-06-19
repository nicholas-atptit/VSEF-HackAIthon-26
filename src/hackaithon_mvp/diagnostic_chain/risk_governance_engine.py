"""Layer 3: risk governance checks for static diagnostic outputs."""

from __future__ import annotations

from .chain_schema import (
    ALLOWED_QUANT_SIGNALS,
    ALLOWED_RISK_LEVELS,
    ALLOWED_SCENARIOS,
    RiskGovernanceOutput,
    assert_allowed,
    assert_no_forbidden_public_terms,
)

RISK_FLAGS = frozenset(
    {
        "insufficient_data",
        "stale_evidence",
        "baseline_not_beaten",
        "model_disagreement",
        "class_imbalance_risk",
        "overfit_risk",
        "final_window_selection_risk",
        "regime_instability",
        "low_liquidity_sensitivity",
        "scope_mismatch",
        "exploratory_only",
    }
)


def run_risk_governance(quant_output: dict, scenario_output: dict) -> RiskGovernanceOutput:
    signal = str(quant_output.get("quant_signal", "insufficient_evidence"))
    scenario = str(scenario_output.get("scenario", "uncertain"))
    consensus = float(quant_output.get("consensus_strength", 0.0))
    completed_count = int(quant_output.get("completed_count", 0))

    risk_flags: list[str] = []
    risk_level = "low"

    if signal not in ALLOWED_QUANT_SIGNALS or scenario not in ALLOWED_SCENARIOS:
        risk_level = "critical"
        risk_flags.append("scope_mismatch")
    elif signal == "insufficient_evidence" or completed_count == 0:
        risk_level = "high"
        risk_flags.append("insufficient_data")
    else:
        if signal == "exploratory_only":
            risk_flags.append("exploratory_only")
            risk_level = "medium"
        if consensus < 0.05:
            risk_flags.append("model_disagreement")
            risk_level = "medium"
        if scenario == "uncertain":
            risk_level = "medium" if risk_level == "low" else risk_level
            if "model_disagreement" not in risk_flags:
                risk_flags.append("model_disagreement")

    if not risk_flags:
        risk_flags.append("baseline_not_beaten")

    if risk_level == "critical":
        risk_action = "Block automated downstream use and require claim-boundary review."
        explanation = "Invalid or mismatched state detected in diagnostic inputs."
    elif risk_level == "high":
        risk_action = "Escalate to human reviewer before downstream diagnostic use."
        explanation = "Evidence is insufficient for a lower risk classification."
    elif risk_level == "medium":
        risk_action = "Keep under reviewer control with conservative downstream handling."
        explanation = "Consensus or scenario quality is limited under static evidence."
    else:
        risk_action = "Allow research workflow continuation under human review."
        explanation = "Static diagnostics do not show a blocking evidence issue."

    assert_allowed(risk_level, ALLOWED_RISK_LEVELS, "risk_level")
    invalid_flags = sorted(set(risk_flags).difference(RISK_FLAGS))
    if invalid_flags:
        raise ValueError(f"unsupported risk flags: {invalid_flags}")

    output: RiskGovernanceOutput = {
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "risk_action": risk_action,
        "explanation": explanation,
    }
    assert_no_forbidden_public_terms(output)
    return output
