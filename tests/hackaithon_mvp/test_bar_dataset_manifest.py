from pathlib import Path

from src.hackaithon_mvp.bar_dataset_manifest import build_bar_dataset_manifest
from src.hackaithon_mvp.timeframe_schema import CANONICAL_TIMEFRAMES


def test_bar_dataset_manifest_defaults_to_30_tickers_and_18_timeframes():
    manifest = build_bar_dataset_manifest("data/market_bars")

    assert manifest["manifest_version"] == "1.0"
    assert manifest["dataset_root"] == "data/market_bars"
    assert manifest["tickers_count"] == 30
    assert manifest["timeframes_count"] == 18
    assert manifest["timeframes"] == list(CANONICAL_TIMEFRAMES)
    assert manifest["partition_columns"] == ["ticker", "timeframe", "date"]
    assert manifest["required_bar_columns"] == [
        "ticker",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert manifest["storage_design"]["canonical_data_format"] == "parquet"
    assert manifest["storage_design"]["planned_query_adapter"] == "duckdb_compatible"
    assert manifest["database_created"] is False
    assert manifest["data_gateway_created"] is False
    assert manifest["live_data_enabled"] is False
    assert manifest["provider_calls_enabled"] is False


def test_bar_dataset_manifest_normalizes_timeframes_without_writing_files(tmp_path):
    manifest = build_bar_dataset_manifest(
        str(tmp_path / "market_bars"),
        tickers=("VCB",),
        timeframe_inputs=("1 ngày", "2h", "1d"),
    )

    assert manifest["tickers"] == ["VCB"]
    assert manifest["timeframes"] == ["1d", "2h"]
    assert not any(Path(tmp_path).rglob("*"))
