from datetime import date, timedelta

from src.hackaithon_mvp.clean_forecast_target_builder import build_clean_direction_targets, render_clean_target_report


def _bars(tickers=("AAA", "BBB"), count=30):
    start = date(2025, 1, 1)
    rows = []
    for ticker in tickers:
        for index in range(count):
            close = 100 + index if ticker == "AAA" else 200 - index
            rows.append(
                {
                    "ticker": ticker,
                    "timestamp": (start + timedelta(days=index)).isoformat(),
                    "open": close - 0.5,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000 + index,
                }
            )
    return rows


def test_clean_targets_are_non_overlapping_and_unique():
    result = build_clean_direction_targets(_bars(count=25), horizons=(5,), non_overlapping=True)

    rows = result["rows"]
    keys = {(row["ticker"], row["horizon"], row["timestamp"]) for row in rows}
    assert result["target_status"] == "ready"
    assert len(keys) == len(rows)
    assert result["dropped_overlapping_windows"] > 0
    assert all(row["actual_timestamp"] > row["forecast_timestamp"] for row in rows)
    assert {row["future_direction"] for row in rows} == {"up", "down"}


def test_clean_targets_can_prioritize_short_horizons():
    result = build_clean_direction_targets(_bars(tickers=("AAA",), count=35), horizons=(1, 5, 10, 20))

    assert result["rows_by_horizon"]["1"] > result["rows_by_horizon"]["5"]
    assert "20" in result["rows_by_horizon"]
    report = render_clean_target_report({key: value for key, value in result.items() if key != "rows"})
    assert "Clean Forecast Target Builder" in report
