from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_RISK_LEVELS
from src.hackaithon_mvp.diagnostic_chain.risk_governance_engine import RISK_FLAGS, run_risk_governance


def test_risk_governance_marks_insufficient_evidence_high_risk():
    output = run_risk_governance(
        {"quant_signal": "insufficient_evidence", "consensus_strength": 0.0, "completed_count": 0},
        {"scenario": "uncertain"},
    )
    assert output["risk_level"] == "high"
    assert "insufficient_data" in output["risk_flags"]


def test_risk_governance_marks_weak_consensus_for_review():
    output = run_risk_governance(
        {"quant_signal": "neutral_or_uncertain", "consensus_strength": 0.01, "completed_count": 1},
        {"scenario": "neutral"},
    )
    assert output["risk_level"] in ALLOWED_RISK_LEVELS
    assert "model_disagreement" in output["risk_flags"]


def test_risk_governance_flags_are_allowed():
    output = run_risk_governance(
        {"quant_signal": "neutral_or_uncertain", "consensus_strength": 0.2, "completed_count": 4},
        {"scenario": "neutral"},
    )
    assert set(output["risk_flags"]).issubset(RISK_FLAGS)
