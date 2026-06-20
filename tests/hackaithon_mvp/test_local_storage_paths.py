import pytest

from src.hackaithon_mvp.local_storage.storage_paths import build_partition_path, normalize_dataset_kind


def test_normalize_dataset_kind_accepts_supported_values():
    assert normalize_dataset_kind(" MARKET_BARS ") == "market_bars"
    assert normalize_dataset_kind("dag_runs") == "dag_runs"


def test_partition_path_normalizes_ticker_and_timeframe():
    path = build_partition_path("data/local", "market_bars", ticker="vcb", timeframe="1 ngày", date="2026-06-20")

    assert path == "data/local/market_bars/ticker=VCB/timeframe=1d/date=2026-06-20/part.parquet"


def test_partition_path_builds_deepest_valid_partial_bar_path():
    assert build_partition_path("data/local", "market_bars", ticker="vcb") == "data/local/market_bars/ticker=VCB"
    assert (
        build_partition_path("data/local", "actual_outcomes", ticker="vcb", timeframe="1 ngày")
        == "data/local/actual_outcomes/ticker=VCB/timeframe=1d"
    )


def test_run_scoped_partition_path_uses_run_id():
    path = build_partition_path("data/local", "dag_runs", run_id="run-001")

    assert path == "data/local/dag_runs/run_id=run-001/part.parquet"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"root": "../data", "dataset_kind": "market_bars"},
        {"root": "data", "dataset_kind": "../market_bars"},
        {"root": "data", "dataset_kind": "market_bars", "ticker": "../VCB"},
        {"root": "data", "dataset_kind": "market_bars", "ticker": "VCB", "timeframe": "3m"},
        {"root": "data", "dataset_kind": "market_bars", "ticker": "VCB", "timeframe": "1d", "date": "20260620"},
        {"root": "data", "dataset_kind": "dag_runs", "run_id": "../run"},
    ],
)
def test_partition_path_rejects_traversal_and_invalid_segments(kwargs):
    with pytest.raises(ValueError):
        build_partition_path(**kwargs)
