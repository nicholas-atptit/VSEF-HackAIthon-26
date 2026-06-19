from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_ROUTES
from src.hackaithon_mvp.diagnostic_chain.phase_router import run_phase_router


def test_phase_router_escalates_high_risk():
    output = run_phase_router(
        {"decision_lane": "watchlist_review"},
        {"risk_level": "high"},
        {"allocation_view": "no_allocation"},
    )
    assert output["route"] == "escalate"
    assert output["human_review_required"] is True


def test_phase_router_handles_insufficient_evidence():
    output = run_phase_router(
        {"decision_lane": "evidence_insufficient"},
        {"risk_level": "high"},
        {"allocation_view": "insufficient_evidence"},
    )
    assert output["route"] == "evidence_insufficient"


def test_phase_router_route_is_allowed():
    output = run_phase_router(
        {"decision_lane": "research_candidate"},
        {"risk_level": "low"},
        {"allocation_view": "research_weight_candidate"},
    )
    assert output["route"] in ALLOWED_ROUTES
