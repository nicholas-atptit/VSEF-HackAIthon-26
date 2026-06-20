from src.hackaithon_mvp.forecast_actual_dag_loop import run_forecast_actual_loop
from src.hackaithon_mvp.local_storage import parquet_adapter
from src.hackaithon_mvp.local_storage.parquet_adapter import read_dataset_records, write_dataset_records


def _forecast():
    return {
        "ticker": "VCB",
        "timeframe": "1d",
        "prediction_timestamp": "2026-01-01T00:00:00+07:00",
        "horizon_steps": 1,
        "forecast_diagnostic": "positive_bias",
    }


def _bars():
    return (
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-01T00:00:00+07:00",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10,
            "volume": 100,
        },
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-02T00:00:00+07:00",
            "open": 12,
            "high": 13,
            "low": 11,
            "close": 12,
            "volume": 100,
        },
    )


def test_no_storage_write_occurs_by_default(tmp_path):
    result = run_forecast_actual_loop(
        forecast_rows=(_forecast(),),
        bar_rows=_bars(),
        storage_root=str(tmp_path),
    )

    assert result["storage_write_enabled"] is False
    assert result["storage_write_summary"]["records_written"] == 0
    assert read_dataset_records(str(tmp_path), "actual_outcomes", ticker="VCB", timeframe="1d", date="2026-01-01") == ()


def test_persist_writes_actual_outcomes_and_evaluation_metrics(tmp_path):
    result = run_forecast_actual_loop(
        forecast_rows=(_forecast(),),
        bar_rows=_bars(),
        storage_root=str(tmp_path),
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
        persist=True,
    )

    assert result["storage_write_enabled"] is True
    assert result["storage_write_summary"]["records_written"] == 2
    assert set(result["storage_write_summary"]["write_results"]) == {"actual_outcomes", "evaluation_metrics"}

    actuals = read_dataset_records(str(tmp_path), "actual_outcomes", ticker="VCB", timeframe="1d", date="2026-01-01")
    metric_run_id = result["storage_write_summary"]["write_results"]["evaluation_metrics"]["requested_path"].split("run_id=")[1].split("/")[0]
    metrics = read_dataset_records(str(tmp_path), "evaluation_metrics", run_id=metric_run_id)

    assert len(actuals) == 1
    assert actuals[0]["source_loop"] == "forecast_actual_dag_loop"
    assert len(metrics) == 1
    assert metrics[0]["rows_total"] == 1


def test_storage_root_can_provide_market_bars(tmp_path):
    write_dataset_records(str(tmp_path), "market_bars", _bars(), ticker="VCB", timeframe="1d", date="2026-01-01")

    result = run_forecast_actual_loop(
        forecast_rows=(_forecast(),),
        storage_root=str(tmp_path),
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
    )

    assert result["storage_context_status"] == "provided"
    assert result["actual_outcome_rows"] == 1


def test_persist_uses_jsonl_fallback_when_parquet_engine_unavailable(monkeypatch, tmp_path):
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

    result = run_forecast_actual_loop(
        forecast_rows=(_forecast(),),
        bar_rows=_bars(),
        storage_root=str(tmp_path),
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
        persist=True,
    )

    assert result["storage_write_summary"]["storage_format"] == "jsonl_fallback"
    for write_result in result["storage_write_summary"]["write_results"].values():
        assert write_result["actual_path"].endswith(".jsonl")
        assert write_result["parquet_engine_available"] is False
