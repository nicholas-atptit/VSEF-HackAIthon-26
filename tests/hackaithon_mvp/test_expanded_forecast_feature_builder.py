from datetime import date, timedelta

from src.hackaithon_mvp.expanded_forecast_feature_builder import (
    build_expanded_forecast_features,
    render_expanded_forecast_feature_report,
)


def _panel(count=40):
    start = date(2026, 1, 1)
    rows = []
    for ticker, sector, offset in (("AAA", "banking", 0), ("BBB", "banking", 5), ("VNINDEX", "index", 10)):
        for index in range(count):
            close = 100 + offset + index * (1 if ticker != "BBB" else -0.25)
            rows.append(
                {
                    "ticker": ticker,
                    "timestamp": (start + timedelta(days=index)).isoformat(),
                    "open": close - 0.2,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "adjusted_close": close * 0.99,
                    "volume": 1000 + index + offset,
                    "turnover": (1000 + index) * close,
                    "foreign_net": 10 + index,
                    "sector": sector,
                    "index_return": 0.001 * (index % 3),
                    "sector_return": 0.002 * (index % 2),
                    "future_direction": "up",
                }
            )
    return rows


def test_expanded_feature_builder_generates_non_leaky_columns():
    result = build_expanded_forecast_features(_panel())
    report = render_expanded_forecast_feature_report({key: value for key, value in result.items() if key != "rows"})

    assert result["feature_status"] == "ready"
    assert "feature_ticker_excess_return_over_index" in result["feature_columns"]
    assert "feature_rolling_beta_to_index" in result["feature_columns"]
    assert "feature_foreign_net_flow_zscore" in result["feature_columns"]
    assert "feature_prior_realized_direction" in result["feature_columns"]
    assert all("future" not in column and "target" not in column and "actual" not in column for column in result["feature_columns"])
    assert "Expanded Forecast Feature Builder" in report


def test_prior_direction_uses_strictly_previous_row():
    rows = build_expanded_forecast_features(_panel(count=4))["rows"]
    aaa = [row for row in rows if row["ticker"] == "AAA"]

    assert aaa[0]["feature_prior_realized_direction"] == 0.0
    assert aaa[2]["feature_prior_realized_direction"] == 1.0
