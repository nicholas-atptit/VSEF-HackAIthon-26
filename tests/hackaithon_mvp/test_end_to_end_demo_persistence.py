from src.hackaithon_mvp.end_to_end_demo import run_end_to_end_demo
from src.hackaithon_mvp.local_storage import parquet_adapter
from src.hackaithon_mvp.local_storage.parquet_adapter import read_dataset_records


def test_no_storage_write_occurs_by_default(tmp_path):
    summary = run_end_to_end_demo(storage_root=str(tmp_path))

    assert summary["storage_write_enabled"] is False
    assert summary["records_written"] == 0
    assert read_dataset_records(str(tmp_path), "actual_outcomes", ticker="DEMO", timeframe="1d", date="2026-01-01") == ()


def test_persistence_writes_only_under_explicit_temp_root(tmp_path):
    summary = run_end_to_end_demo(persist=True, storage_root=str(tmp_path))

    assert summary["storage_write_enabled"] is True
    assert summary["records_written"] == 2
    actuals = read_dataset_records(str(tmp_path), "actual_outcomes", ticker="DEMO", timeframe="1d", date="2026-01-01")
    assert len(actuals) == 1
    assert actuals[0]["ticker"] == "DEMO"
    assert actuals[0]["source_loop"] == "forecast_actual_dag_loop"


def test_jsonl_fallback_is_acceptable(monkeypatch, tmp_path):
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

    summary = run_end_to_end_demo(persist=True, storage_root=str(tmp_path))

    assert summary["storage_format"] == "jsonl_fallback"
    assert summary["records_written"] == 2
