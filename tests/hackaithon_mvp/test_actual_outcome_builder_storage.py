from src.hackaithon_mvp.actual_outcome_builder import build_actual_outcomes_from_storage
from src.hackaithon_mvp.local_storage.parquet_adapter import write_dataset_records


def test_storage_helper_reads_local_market_bars(tmp_path):
    forecasts = (
        {
            "ticker": "VCB",
            "timeframe": "1 ngày",
            "prediction_timestamp": "2026-01-01T00:00:00+07:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
        },
    )
    bars = (
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
    write_dataset_records(str(tmp_path), "market_bars", bars, ticker="VCB", timeframe="1d", date="2026-01-01")

    rows = build_actual_outcomes_from_storage(
        forecasts,
        storage_root=str(tmp_path),
        ticker="vcb",
        timeframe="1 ngày",
        date="2026-01-01",
    )

    assert len(rows) == 1
    assert rows[0]["actual_direction_label"] == "positive"


def test_storage_helper_returns_empty_when_no_local_bars_exist(tmp_path):
    rows = build_actual_outcomes_from_storage(
        (
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "prediction_timestamp": "2026-01-01T00:00:00+07:00",
                "horizon_steps": 1,
                "forecast_diagnostic": "positive_bias",
            },
        ),
        storage_root=str(tmp_path),
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
    )

    assert rows == ()
