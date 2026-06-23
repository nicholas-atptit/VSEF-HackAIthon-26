import json

from src.hackaithon_mvp.local_training_dataset_builder import (
    build_supervised_direction_dataset,
    discover_local_ohlcv_sources,
    normalize_ohlcv_rows,
)


def _bars(tickers=("AAA", "VN30"), count=80):
    rows = []
    for ticker_index, ticker in enumerate(tickers):
        for index in range(count):
            close = 100 + ticker_index * 5 + index * 0.2 + ((index % 7) - 3) * 0.3
            rows.append(
                {
                    "date": f"2025-01-{index + 1:02d}",
                    "ticker": ticker,
                    "open": close - 0.1,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": 1000 + index,
                }
            )
    return rows


def test_normalize_ohlcv_rows_aliases_and_drops_invalid():
    rows = [
        {"date": "2025-01-01", "symbol": "aaa", "o": 1, "h": 2, "l": 1, "c": 1.5, "v": 10},
        {"date": "2025-01-02", "symbol": "aaa", "o": 1, "h": 0, "l": 2, "c": 1.5, "v": 10},
    ]

    normalized = normalize_ohlcv_rows(rows)

    assert len(normalized) == 1
    assert normalized[0]["ticker"] == "AAA"


def test_build_supervised_dataset_uses_future_targets_and_past_features():
    result = build_supervised_direction_dataset(_bars(), horizons=(1, 5))

    assert result["dataset_status"] == "ready"
    assert result["ticker_count"] == 2
    assert result["dataset_row_count"] > 0
    first = result["rows"][0]
    assert "future_return" in first
    assert "feature_lag_return_1" in first
    assert "feature_lag_return_20" in first
    assert "feature_rolling_volatility_40" in first
    assert "feature_ticker_relative_return_zscore" in first
    assert "feature_cross_sectional_return_rank" in first
    assert "feature_market_equal_weight_return" in first
    assert "market_relative_direction" in next(row for row in result["rows"] if row["ticker"] == "AAA")
    assert all(column.startswith("feature_") for column in result["feature_columns"])


def test_discover_local_ohlcv_sources_on_tmp_repo(tmp_path):
    path = tmp_path / "AAA.csv"
    path.write_text(
        "date,ticker,open,high,low,close,volume\n2025-01-01,AAA,1,2,1,2,100\n",
        encoding="utf-8",
    )

    result = discover_local_ohlcv_sources(repo_root=str(tmp_path))

    assert result["candidate_file_count"] == 1
    assert result["candidate_files"][0]["path"] == "AAA.csv"


def test_dataset_write_shape_is_json_serializable():
    result = build_supervised_direction_dataset(_bars(count=90), horizons=(1,))

    json.dumps({key: value for key, value in result.items() if key != "rows"})
