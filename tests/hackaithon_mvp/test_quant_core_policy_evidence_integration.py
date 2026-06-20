from src.hackaithon_mvp.diagnostic_report import render_diagnostic_report
from src.hackaithon_mvp.evidence_packet import build_evidence_packet


def _chain_output_with_policy():
    return {
        "ticker": "AAA",
        "timeframe": "1h",
        "layer_1_quant_core": {
            "quant_signal": "positive_bias",
            "consensus_strength": 0.4,
            "engine_count_checked": 1,
            "completed_count": 1,
            "skipped_missing_evidence_count": 0,
            "forecast_diagnostic_engine_enabled": True,
            "forecast_diagnostic_counts": {
                "positive": 1,
                "negative": 0,
                "neutral": 0,
                "insufficient": 0,
                "exploratory": 0,
            },
            "forecast_diagnostic_sample": [],
            "policy_id": "quant_core_policy.pva.eligible_slice_gate.v1",
            "policy_name": "eligible_slice_gate_bacc_0.600",
            "policy_runtime_status": "directional_allowed",
            "pre_policy_forecast_diagnostic": "positive_bias",
            "policy_validation_accuracy": 0.534888,
            "policy_validation_balanced_accuracy": 0.532707,
            "policy_validation_coverage": 0.16269,
        },
        "layer_2_scenario": {"scenario": "uncertain", "scenario_confidence": 0.4},
        "layer_3_risk_governance": {"risk_level": "medium", "risk_flags": [], "risk_action": "human_review"},
        "layer_4_decision_lane": {"decision_lane": "review", "decision_action": "human_review"},
        "layer_5_market_context": {"market_context_status": "static_context_only"},
        "layer_6_calibration": {"calibrated_confidence": 0.4, "calibration_policy": "static"},
        "review_cycle": {"cycle_mode": "human_review"},
        "layer_7_portfolio_diagnostic_allocator": {"allocation_view": "research_only"},
        "layer_8_phase_router": {"route": "route_candidate", "dashboard_status": "review"},
    }


def test_evidence_packet_can_carry_optional_policy_metadata():
    packet = build_evidence_packet(
        _chain_output_with_policy(),
        run_metadata={"run_id": "policy-run", "generated_at": "2026-06-20T00:00:00+00:00"},
    )

    assert packet["policy_metadata"]["policy_id"] == "quant_core_policy.pva.eligible_slice_gate.v1"
    assert packet["policy_metadata"]["policy_runtime_status"] == "directional_allowed"
    assert packet["policy_metadata"]["policy_validation_balanced_accuracy"] == 0.532707


def test_diagnostic_report_renders_optional_policy_metadata():
    packet = build_evidence_packet(
        _chain_output_with_policy(),
        run_metadata={"run_id": "policy-run", "generated_at": "2026-06-20T00:00:00+00:00"},
    )

    report = render_diagnostic_report(packet)

    assert "## Quant Core Policy" in report
    assert "Policy ID: quant_core_policy.pva.eligible_slice_gate.v1" in report
    assert "Validation balanced accuracy: 0.532707" in report
