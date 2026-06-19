import pytest

from src.hackaithon_mvp.diagnostic_chain.chain_schema import (
    ALLOWED_ALLOCATION_VIEWS,
    ALLOWED_DECISION_LANES,
    ALLOWED_QUANT_SIGNALS,
    ALLOWED_RISK_LEVELS,
    ALLOWED_ROUTES,
    ALLOWED_SCENARIOS,
    DiagnosticChainOutput,
    NON_CLAIM_TEXT,
    assert_no_forbidden_public_terms,
)


def test_schema_allowed_label_sets_include_required_values():
    assert "neutral_or_uncertain" in ALLOWED_QUANT_SIGNALS
    assert "uncertain" in ALLOWED_SCENARIOS
    assert "critical" in ALLOWED_RISK_LEVELS
    assert "evidence_insufficient" in ALLOWED_DECISION_LANES
    assert "risk_capped_candidate" in ALLOWED_ALLOCATION_VIEWS
    assert "route_candidate" in ALLOWED_ROUTES


def test_schema_validator_rejects_forbidden_public_wording():
    with pytest.raises(ValueError):
        assert_no_forbidden_public_terms({"public_text": "This is a trading signal."})


def test_diagnostic_chain_output_dataclass_serializes_nested_layers():
    output = DiagnosticChainOutput(
        ticker="VCB",
        layer_1_quant_core={
            "ticker": "VCB",
            "quant_signal": "neutral_or_uncertain",
            "consensus_strength": 0.1,
            "engine_count_checked": 10,
            "completed_count": 1,
            "skipped_missing_evidence_count": 9,
            "warnings": [],
            "non_claim": NON_CLAIM_TEXT,
        },
        layer_2_scenario={
            "scenario": "neutral",
            "scenario_probabilities": {"growth": 0.1, "neutral": 0.7, "correction": 0.1, "uncertain": 0.1},
            "scenario_confidence": 0.7,
            "explanation": "Static scenario label.",
        },
        layer_3_risk_governance={"risk_level": "medium", "risk_flags": [], "risk_action": "Review.", "explanation": "Static."},
        layer_4_decision_lane={
            "decision_lane": "watchlist_review",
            "reason": "Static review.",
            "human_review_required": True,
            "non_claim": NON_CLAIM_TEXT,
        },
        layer_5_market_context={
            "market_context_status": "static_placeholder",
            "context_label": "local_context_unavailable",
            "context_notes": [],
            "live_context_enabled": False,
            "non_claim": NON_CLAIM_TEXT,
        },
        layer_6_calibration={
            "calibrated_confidence": 0.1,
            "calibration_policy": "static_confidence_adjustment_only",
            "fine_tuning_performed": False,
            "explanation": "Static adjustment.",
        },
        review_cycle={
            "cycle_mode": "manual_static_review",
            "layers_completed": [],
            "non_realtime_claim": "Manual static review cycle only.",
            "timestamp": "2026-06-20T00:00:00+00:00",
        },
        layer_7_portfolio_diagnostic_allocator={
            "allocation_view": "risk_capped_candidate",
            "max_research_weight": 0.01,
            "allocation_is_advisory": False,
            "explanation": "Research sizing view.",
            "non_claim": NON_CLAIM_TEXT,
        },
        layer_8_phase_router={
            "route": "maintain_watchlist_review",
            "dashboard_status": "not_enabled_for_this_slice",
            "human_review_required": True,
            "explanation": "Static route.",
            "non_claim": NON_CLAIM_TEXT,
        },
        non_claim=NON_CLAIM_TEXT,
    ).to_dict()
    assert output["ticker"] == "VCB"
    assert_no_forbidden_public_terms(output)
