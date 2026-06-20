from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_storage_bridge import persist_dag_execution
from src.hackaithon_mvp.local_storage import parquet_adapter


def _execution_result():
    return execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
    )


def test_persist_dag_execution_writes_compact_records_under_temp_root(tmp_path):
    result = _execution_result()
    persistence = persist_dag_execution(result, storage_root=str(tmp_path))

    assert persistence["storage_write_enabled"] is True
    assert persistence["records_written"] == 3
    assert set(persistence["write_results"]) == {"dag_runs", "evidence_packets", "diagnostic_reports"}
    for write_result in persistence["write_results"].values():
        assert str(write_result["actual_path"]).startswith(str(tmp_path).replace("\\", "/"))
        assert write_result["row_count"] == 1

    run_records = parquet_adapter.read_dataset_records(str(tmp_path), "dag_runs", run_id=result["run_id"])
    packet_records = parquet_adapter.read_dataset_records(str(tmp_path), "evidence_packets", run_id=result["run_id"])
    report_records = parquet_adapter.read_dataset_records(str(tmp_path), "diagnostic_reports", run_id=result["run_id"])

    assert len(run_records) == 1
    assert len(packet_records) == 1
    assert len(report_records) == 1
    assert "final_state" not in run_records[0]
    assert packet_records[0]["artifact_kind"] == "evidence_packet"
    assert report_records[0]["artifact_kind"] == "diagnostic_report"


def test_persist_dag_execution_uses_jsonl_fallback_when_parquet_engine_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(
        parquet_adapter,
        "detect_parquet_capability",
        lambda: {
            "pandas_available": False,
            "parquet_engine": None,
            "parquet_engine_available": False,
            "storage_format": "jsonl_fallback",
            "fallback_format": "jsonl",
            "claim_boundary": {},
            "non_claim": "test fallback",
        },
    )
    result = _execution_result()
    persistence = persist_dag_execution(result, storage_root=str(tmp_path))

    assert persistence["storage_format"] == "jsonl_fallback"
    for write_result in persistence["write_results"].values():
        assert write_result["actual_path"].endswith(".jsonl")
        assert write_result["parquet_engine_available"] is False
