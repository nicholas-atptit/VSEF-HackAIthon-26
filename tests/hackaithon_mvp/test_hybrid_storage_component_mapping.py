from src.hackaithon_mvp.hybrid_storage_architecture import (
    compare_storage_options,
    map_diagnostic_components_to_storage,
)


def test_diagnostic_components_have_storage_mappings():
    mapping = map_diagnostic_components_to_storage()
    mappings = mapping["mappings"]

    expected = {
        "static_evidence_loader": ["local_storage", "canonical_data_lake"],
        "engine_runtime": ["engine_registry", "run_registry"],
        "forecast_diagnostic_engine": ["forecast_outputs"],
        "quant_core_policy_runtime": ["policy_registry", "forecast_outputs"],
        "scenario_engine": ["dag_runs", "chain_outputs"],
        "risk_governance_engine": ["audit_log", "risk_flags"],
        "decision_lane_engine": ["review_state", "chain_outputs"],
        "market_context_engine": ["context_snapshots_later"],
        "calibration_engine": ["calibration_outputs"],
        "research_allocation_view": ["research_sizing_outputs"],
        "phase_router": ["routing_outputs", "review_state"],
        "evidence_packet": ["evidence_packets"],
        "diagnostic_report": ["diagnostic_reports"],
        "forecast_vs_actual_evaluation": ["actual_outcomes", "evaluation_metrics"],
        "diagnostic_dag_runtime": ["dag_runs", "audit_log"],
    }

    assert mappings == expected
    assert mapping["component_count"] == len(expected)


def test_storage_option_comparison_includes_required_options():
    comparison = compare_storage_options()
    options = comparison["options"]

    assert set(options) == {
        "local_partitioned_file_adapter",
        "lakehouse_target",
        "metadata_store_server_db",
        "serving_layer_optional",
        "hybrid_target",
    }
    assert comparison["recommended_current"] == "local_partitioned_file_adapter"
    assert comparison["recommended_target"] == "hybrid_storage_architecture"
    for option in options.values():
        assert set(option) == {
            "role",
            "local_mvp_fit",
            "server_fit",
            "cloud_scale_fit",
            "complexity",
            "current_status",
            "recommended_phase",
        }
        assert option["complexity"] in {"low", "medium", "high", "very_high"}
