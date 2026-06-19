from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_ALLOCATION_VIEWS
from src.hackaithon_mvp.diagnostic_chain.portfolio_diagnostic_allocator import run_portfolio_diagnostic_allocator


def test_allocator_is_not_advisory_and_handles_insufficient_evidence():
    output = run_portfolio_diagnostic_allocator(
        {"decision_lane": "evidence_insufficient"},
        {"risk_level": "high"},
        {"calibrated_confidence": 0.0},
    )
    assert output["allocation_view"] == "insufficient_evidence"
    assert output["allocation_is_advisory"] is False


def test_allocator_returns_risk_capped_candidate_for_medium_risk():
    output = run_portfolio_diagnostic_allocator(
        {"decision_lane": "watchlist_review"},
        {"risk_level": "medium"},
        {"calibrated_confidence": 0.4},
    )
    assert output["allocation_view"] == "risk_capped_candidate"
    assert output["allocation_view"] in ALLOWED_ALLOCATION_VIEWS


def test_allocator_returns_research_weight_candidate_for_low_risk_candidate():
    output = run_portfolio_diagnostic_allocator(
        {"decision_lane": "research_candidate"},
        {"risk_level": "low"},
        {"calibrated_confidence": 0.5},
    )
    assert output["allocation_view"] == "research_weight_candidate"
