from datetime import date, timedelta

from src.hackaithon_mvp.forecast_edge_feature_builder import (
    build_cross_sectional_features,
    build_forecast_edge_features,
    build_technical_features,
    render_forecast_edge_feature_report,
)


def _bars(count=35):
    start = date(2025, 1, 1)
    rows = []
    for ticker_offset, ticker in enumerate(("AAA", "BBB", "CCC")):
        for index in range(count):
            close = 100 + ticker_offset * 10 + index * (1 if ticker != "BBB" else -0.5)
            rows.append(
                {
                    "ticker": ticker,
                    "timestamp": (start + timedelta(days=index)).isoformat(),
                    "open": close - 0.25,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000 + ticker_offset * 100 + index,
                    "future_direction": "up",
                }
            )
    return rows


def test_feature_builder_generates_expected_non_leaky_columns():
    result = build_forecast_edge_features(_bars())

    assert result["feature_status"] == "ready"
    assert {"market_context", "liquidity", "technical", "cross_sectional"}.issubset(set(result["feature_blocks"]))
    assert "feature_ticker_excess_return_vs_market" in result["feature_columns"]
    assert "feature_previous_realized_direction" in result["feature_columns"]
    assert all("future" not in column and "target" not in column for column in result["feature_columns"])
    report = render_forecast_edge_feature_report({key: value for key, value in result.items() if key != "rows"})
    assert "Forecast Edge Feature Builder" in report


def test_previous_direction_uses_prior_timestamp_only():
    rows = build_technical_features(_bars(count=5))["rows"]
    aaa = [row for row in rows if row["ticker"] == "AAA"]

    assert aaa[0]["feature_previous_realized_direction"] == 0.0
    assert aaa[2]["feature_previous_realized_direction"] == 1.0


def test_cross_sectional_ranks_use_same_timestamp_panel():
    result = build_cross_sectional_features(_bars(count=4))
    first_time = min(row["timestamp"] for row in result["rows"])
    panel = [row for row in result["rows"] if row["timestamp"] == first_time]

    assert len(panel) == 3
    assert all(0.0 <= row["feature_cross_sectional_volume_rank"] <= 1.0 for row in panel)
