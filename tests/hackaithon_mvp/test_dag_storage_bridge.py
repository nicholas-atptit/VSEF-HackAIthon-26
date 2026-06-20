from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_storage_bridge import (
    build_dag_artifact_records,
    build_dag_node_records,
    build_dag_run_record,
)
from src.hackaithon_mvp.quant_core_policy_registry import get_demo_policy_h40_direction_only


def _execution_result(policy=None):
    return execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
        policy=policy,
    )


def test_dag_run_record_is_compact_and_valid():
    policy = get_demo_policy_h40_direction_only()
    result = _execution_result(policy=policy)
    record = build_dag_run_record(result)

    assert record["run_id"] == result["run_id"]
    assert record["ticker"] == "VCB"
    assert record["timeframe"] == "1d"
    assert record["node_count"] == len(result["node_results"])
    assert record["policy_id"] == policy["policy_id"]
    assert record["policy_name"] == policy["policy_name"]
    assert record["policy_runtime_status"] == "non_directional_preserved"
    assert "final_state" not in record
    assert "node_results" not in record
    assert record["claim_boundary"]["storage_write_default"] is False


def test_dag_node_records_are_created_without_raw_outputs():
    result = _execution_result()
    records = build_dag_node_records(result)

    assert len(records) == len(result["node_results"])
    assert records[0]["node_id"] == "static_evidence_loader"
    assert records[0]["node_name"] == "Static Evidence Loader"
    assert records[0]["status"] == "completed"
    assert isinstance(records[0]["produces"], list)
    assert "outputs" not in records[0]


def test_artifact_records_include_evidence_and_report_when_available():
    policy = get_demo_policy_h40_direction_only()
    result = _execution_result(policy=policy)
    records = build_dag_artifact_records(result)

    assert set(records) == {"dag_runs", "evidence_packets", "diagnostic_reports"}
    assert len(records["dag_runs"]) == 1
    assert len(records["evidence_packets"]) == 1
    assert len(records["diagnostic_reports"]) == 1
    packet = records["evidence_packets"][0]
    report = records["diagnostic_reports"][0]
    assert packet["policy_id"] == policy["policy_id"]
    assert packet["pre_policy_forecast_diagnostic"] == "neutral_or_uncertain"
    assert packet["policy_validation_balanced_accuracy"] == 0.68537
    assert report["has_policy_section"] is True


def test_artifact_records_preserve_policy_and_storage_context_metadata():
    policy = get_demo_policy_h40_direction_only()
    result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
        policy=policy,
        storage_context={
            "storage_context_status": "provided",
            "market_bar_count": 2,
        },
    )
    records = build_dag_artifact_records(result)
    packet = records["evidence_packets"][0]
    report = records["diagnostic_reports"][0]

    for record in (packet, report):
        assert record["policy_id"] == policy["policy_id"]
        assert record["policy_validation_accuracy"] == 0.738202
        assert record["storage_context_status"] == "provided"
        assert record["market_bar_count"] == 2
