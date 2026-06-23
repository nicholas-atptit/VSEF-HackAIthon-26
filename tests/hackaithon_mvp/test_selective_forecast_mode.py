from datetime import date, timedelta

from src.hackaithon_mvp.selective_forecast_mode import (
    build_selective_forecast_policy,
    evaluate_selective_forecast_policy,
    render_selective_forecast_mode_report,
)


def _rows(count=30, *, ticker="AAA", correct=True):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        predicted = actual if correct else ("down" if actual == "up" else "up")
        forecast_day = start + timedelta(days=index)
        rows.append(
            {
                "ticker": ticker,
                "model_id": "m1",
                "horizon": 1,
                "forecast_timestamp": forecast_day.isoformat(),
                "actual_timestamp": (forecast_day + timedelta(days=1)).isoformat(),
                "predicted_direction": predicted,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
                "deoverlap_step_index": index,
            }
        )
    return rows


def test_selective_forecast_policy_retains_only_allowed_slice_payloads():
    rows = _rows(30, ticker="AAA") + _rows(5, ticker="BBB")
    policy = build_selective_forecast_policy(rows, min_rows=10)
    result = evaluate_selective_forecast_policy(rows, policy)

    assert policy["allowed_slice_count"] == 1
    assert policy["abstained_slice_count"] == 1
    assert isinstance(result["retained_rows"], list)
    assert result["retained_row_count"] == 30
    assert result["abstained_rows"] == 5
    assert result["forecast_coverage"] == 0.857143
    assert result["global_retained_balanced_accuracy"] == 1.0
    assert all(row["selective_forecast_status"] == "diagnostic forecast retained" for row in result["retained_rows"])


def test_selective_forecast_report_uses_diagnostic_abstention_language():
    rows = _rows(30, ticker="AAA") + _rows(5, ticker="BBB")
    policy = build_selective_forecast_policy(rows, min_rows=10)
    public = evaluate_selective_forecast_policy(rows, policy)
    public["retained_rows"] = len(public["retained_rows"])
    report = render_selective_forecast_mode_report(public).lower()

    assert "diagnostic forecast retained" in report
    assert "abstained due to insufficient evidence" in report
    assert "human review required" in report
    for forbidden in ("buy", "sell", "trading signal"):
        assert forbidden not in report
