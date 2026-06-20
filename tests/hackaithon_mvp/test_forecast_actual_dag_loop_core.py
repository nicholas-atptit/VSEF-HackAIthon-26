from src.hackaithon_mvp.forecast_actual_dag_loop import (
    build_actual_outcome_storage_records,
    build_evaluation_metric_record,
    run_forecast_actual_loop,
)


def _forecast(timestamp="2026-01-01T00:00:00+07:00", diagnostic="positive_bias", score=0.9):
    return {
        "ticker": "VCB",
        "timeframe": "1d",
        "prediction_timestamp": timestamp,
        "horizon_steps": 1,
        "forecast_diagnostic": diagnostic,
        "diagnostic_score": score,
        "model_family": "classification",
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
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-03T00:00:00+07:00",
            "open": 11,
            "high": 12,
            "low": 10,
            "close": 11,
            "volume": 100,
        },
    )


def test_loop_builds_actual_outcomes_and_evaluates_metrics():
    result = run_forecast_actual_loop(
        forecast_rows=(_forecast(), _forecast("2026-01-02T00:00:00+07:00", "negative_bias", 0.8)),
        bar_rows=_bars(),
        top_k=1,
    )

    assert result["loop_status"] == "completed"
    assert result["actual_outcome_rows"] == 2
    assert result["skipped_forecast_rows"] == 0
    assert result["evaluation"]["actual_data_status"] == "provided"
    assert result["evaluation"]["rows_total"] == 2
    assert result["evaluation"]["top_k_summary"]["top_k"] == 1
    assert result["storage_write_enabled"] is False
    assert result["storage_write_summary"]["records_written"] == 0


def test_missing_bars_return_safe_missing_status():
    result = run_forecast_actual_loop(forecast_rows=(_forecast(),))

    assert result["loop_status"] == "missing_bars"
    assert result["actual_outcome_status"] == "missing_bars"
    assert result["evaluation_status"] == "not_run"
    assert result["actual_outcome_rows"] == 0
    assert result["skipped_forecast_rows"] == 1


def test_missing_future_bars_are_skipped_not_fabricated():
    result = run_forecast_actual_loop(
        forecast_rows=(_forecast("2026-01-03T00:00:00+07:00"),),
        bar_rows=_bars(),
    )

    assert result["loop_status"] == "completed"
    assert result["actual_outcome_rows"] == 0
    assert result["skipped_forecast_rows"] == 1
    assert result["evaluation"]["actual_data_status"] == "missing"


def test_exact_and_nearest_prior_matching():
    exact = run_forecast_actual_loop(
        forecast_rows=(_forecast("2026-01-01T12:00:00+07:00"),),
        bar_rows=_bars(),
        match_mode="exact",
    )
    nearest = run_forecast_actual_loop(
        forecast_rows=(_forecast("2026-01-01T12:00:00+07:00"),),
        bar_rows=_bars(),
        match_mode="nearest_prior",
    )

    assert exact["actual_outcome_rows"] == 0
    assert nearest["actual_outcome_rows"] == 1


def test_storage_record_builders_are_compact():
    result = run_forecast_actual_loop(forecast_rows=(_forecast(),), bar_rows=_bars())
    rows = build_actual_outcome_storage_records(
        (
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "prediction_timestamp": "2026-01-01T00:00:00+07:00",
                "actual_timestamp": "2026-01-02T00:00:00+07:00",
                "horizon_steps": 1,
                "forecast_diagnostic": "positive_bias",
                "actual_future_return": 0.2,
                "actual_direction_label": "positive",
                "engine_id": "demo",
            },
        )
    )
    metric = build_evaluation_metric_record(result["evaluation"], run_id="demo_run")

    assert rows[0]["source_loop"] == "forecast_actual_dag_loop"
    assert rows[0]["engine_id"] == "demo"
    assert "bar_rows" not in rows[0]
    assert metric["run_id"] == "demo_run"
    assert metric["rows_total"] == 1
