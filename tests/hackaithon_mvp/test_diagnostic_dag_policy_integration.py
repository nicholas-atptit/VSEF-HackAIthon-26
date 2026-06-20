from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.quant_core_policy_registry import get_demo_policy_h40_direction_only


def test_dag_execution_completes_with_h40_demo_policy():
    policy = get_demo_policy_h40_direction_only()
    result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {
            "ticker": "VCB",
            "timeframe": "1 ngày",
            "horizon_steps": 1,
            "policy_id": policy["policy_id"],
            "policy_name": policy["policy_name"],
        },
        policy=policy,
    )

    assert result["execution_status"] == "completed_with_warnings"
    assert result["final_state"]["policy_metadata"]["policy_id"] == "quant_core_policy.h40.eligible_slice_gate.v1"
    assert result["final_state"]["policy_metadata"]["policy_validation_balanced_accuracy"] == 0.68537


def test_policy_metadata_reaches_evidence_packet_and_report():
    policy = get_demo_policy_h40_direction_only()
    result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
        policy=policy,
    )

    packet_policy = result["final_state"]["evidence_packet"]["policy_metadata"]

    assert packet_policy["policy_id"] == policy["policy_id"]
    assert packet_policy["pre_policy_forecast_diagnostic"] == "neutral_or_uncertain"
    assert packet_policy["policy_runtime_status"] == "non_directional_preserved"
    assert result["final_state"]["diagnostic_report"]["has_policy_section"] is True
