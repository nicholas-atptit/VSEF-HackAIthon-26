from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_DECISION_LANES
from src.hackaithon_mvp.diagnostic_chain.decision_lane_engine import run_decision_lane


def test_decision_lane_uses_evidence_insufficient_first():
    output = run_decision_lane(
        {"quant_signal": "insufficient_evidence", "consensus_strength": 0.0},
        {"scenario": "uncertain"},
        {"risk_level": "high", "risk_flags": ["insufficient_data"]},
    )
    assert output["decision_lane"] == "evidence_insufficient"
    assert output["human_review_required"] is True


def test_decision_lane_escalates_high_risk():
    output = run_decision_lane(
        {"quant_signal": "neutral_or_uncertain", "consensus_strength": 0.1},
        {"scenario": "neutral"},
        {"risk_level": "high", "risk_flags": []},
    )
    assert output["decision_lane"] == "escalate_for_review"


def test_decision_lane_returns_allowed_label():
    output = run_decision_lane(
        {"quant_signal": "positive_bias", "consensus_strength": 0.3},
        {"scenario": "growth"},
        {"risk_level": "low", "risk_flags": []},
    )
    assert output["decision_lane"] in ALLOWED_DECISION_LANES
