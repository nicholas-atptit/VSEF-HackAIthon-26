from datetime import date, timedelta

from src.hackaithon_mvp.narrow_forecast_target_selector import (
    render_narrow_forecast_target_selector_report,
    select_narrow_forecast_targets,
)


def _rows(count=520, ticker="AAA", horizon=1):
    start = date(2026, 1, 1)
    rows = []
    for index in range(count):
        rows.append(
            {
                "ticker": ticker,
                "horizon": horizon,
                "timestamp": (start + timedelta(days=index)).isoformat(),
                "future_direction": "up" if index % 2 == 0 else "down",
                "non_overlapping_target": True,
            }
        )
    return rows


def test_narrow_selector_allows_balanced_preferred_slice():
    result = select_narrow_forecast_targets(_rows(), min_rows=500)
    report = render_narrow_forecast_target_selector_report(result)

    assert result["selection_status"] == "ready"
    assert result["allowed_count"] == 1
    assert result["recommended_forecast_universe"][0]["ticker"] == "AAA"
    assert "Narrow Forecast Target Selector" in report


def test_narrow_selector_marks_small_slice_exploratory():
    result = select_narrow_forecast_targets(_rows(count=180), min_rows=500)

    assert result["allowed_count"] == 0
    assert result["exploratory_count"] == 1


def test_narrow_selector_rejects_extreme_class_balance():
    rows = _rows()
    for row in rows:
        row["future_direction"] = "up"

    result = select_narrow_forecast_targets(rows, min_rows=500)

    assert result["allowed_count"] == 0
    assert result["rejected_count"] == 1
    assert "single_class_slice" in result["rejected_target_candidates"][0]["rejection_reasons"]
