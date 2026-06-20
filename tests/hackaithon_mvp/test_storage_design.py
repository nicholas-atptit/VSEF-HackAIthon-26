import pytest

from src.hackaithon_mvp.storage_design import (
    CANONICAL_DATA_FORMAT,
    PARTITION_COLUMNS,
    PLANNED_QUERY_ADAPTER,
    REQUIRED_BAR_COLUMNS,
    STORAGE_BACKEND_DECISION,
    build_partition_path,
    get_storage_design,
)


def test_storage_design_contract_flags_and_columns():
    design = get_storage_design()

    assert design["decision"] == STORAGE_BACKEND_DECISION
    assert design["canonical_data_format"] == "parquet"
    assert CANONICAL_DATA_FORMAT == "parquet"
    assert design["planned_query_adapter"] == "duckdb_compatible"
    assert PLANNED_QUERY_ADAPTER == "duckdb_compatible"
    assert design["partition_columns"] == ["ticker", "timeframe", "date"]
    assert PARTITION_COLUMNS == ("ticker", "timeframe", "date")
    assert design["required_bar_columns"] == [
        "ticker",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert REQUIRED_BAR_COLUMNS[-1] == "volume"
    assert design["database_created"] is False
    assert design["data_gateway_created"] is False
    assert design["live_data_enabled"] is False
    assert design["provider_calls_enabled"] is False


def test_partition_path_normalizes_ticker_and_timeframe():
    path = build_partition_path("data/market_bars", "vcb", "1 ngày", "2026-06-20")

    assert path == "data/market_bars/ticker=VCB/timeframe=1d/date=2026-06-20/bars.parquet"


@pytest.mark.parametrize(
    ("ticker", "timeframe", "date"),
    [
        ("", "1d", "2026-06-20"),
        ("../VCB", "1d", "2026-06-20"),
        ("VCB", "3m", "2026-06-20"),
        ("VCB", "1d", ""),
        ("VCB", "1d", "../2026-06-20"),
        ("VCB", "1d", "20260620"),
    ],
)
def test_partition_path_rejects_invalid_segments(ticker, timeframe, date):
    with pytest.raises(ValueError):
        build_partition_path("data/market_bars", ticker, timeframe, date)
