"""Layer 2: scenario classification from bounded quant diagnostics."""

from __future__ import annotations

from .chain_schema import (
    ALLOWED_SCENARIOS,
    ScenarioOutput,
    assert_allowed,
    assert_no_forbidden_public_terms,
)


def _probabilities(scenario: str, confidence: float) -> dict[str, float]:
    base = {"growth": 0.2, "neutral": 0.3, "correction": 0.2, "uncertain": 0.3}
    if scenario == "growth":
        base = {"growth": confidence, "neutral": 0.2, "correction": 0.1, "uncertain": round(0.7 - confidence, 6)}
    elif scenario == "correction":
        base = {"growth": 0.1, "neutral": 0.2, "correction": confidence, "uncertain": round(0.7 - confidence, 6)}
    elif scenario == "neutral":
        base = {"growth": 0.15, "neutral": confidence, "correction": 0.15, "uncertain": round(0.7 - confidence, 6)}
    total = sum(base.values())
    return {key: round(value / total, 6) for key, value in base.items()}


def run_scenario_engine(quant_output: dict) -> ScenarioOutput:
    signal = str(quant_output.get("quant_signal", "insufficient_evidence"))
    consensus = float(quant_output.get("consensus_strength", 0.0))

    if signal == "insufficient_evidence":
        scenario = "uncertain"
        confidence = 0.2
        explanation = "Local sample evidence is not sufficient for a directional scenario label."
    elif consensus < 0.05:
        scenario = "uncertain" if signal in {"positive_bias", "negative_bias"} else "neutral"
        confidence = 0.3
        explanation = "Consensus is weak, so the scenario remains conservative."
    elif signal == "positive_bias":
        scenario = "growth"
        confidence = min(0.7, 0.45 + consensus)
        explanation = "Positive diagnostic bias is present within the static evidence boundary."
    elif signal == "negative_bias":
        scenario = "correction"
        confidence = min(0.7, 0.45 + consensus)
        explanation = "Negative diagnostic bias is present within the static evidence boundary."
    else:
        scenario = "neutral"
        confidence = min(0.6, 0.35 + consensus)
        explanation = "The quant summary does not support a stronger scenario label."

    assert_allowed(scenario, ALLOWED_SCENARIOS, "scenario")
    output: ScenarioOutput = {
        "scenario": scenario,
        "scenario_probabilities": _probabilities(scenario, confidence),
        "scenario_confidence": round(confidence, 6),
        "explanation": explanation,
    }
    assert_no_forbidden_public_terms(output)
    return output
