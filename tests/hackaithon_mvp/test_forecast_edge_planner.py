from datetime import date, timedelta

from src.hackaithon_mvp.forecast_edge_planner import build_forecast_edge_plan, render_forecast_edge_plan_report


def _bars():
    start = date(2025, 1, 1)
    rows = []
    for ticker in ("AAA", "BBB", "CCC", "DDD", "EEE"):
        for index in range(40):
            rows.append(
                {
                    "ticker": ticker,
                    "timestamp": (start + timedelta(days=index)).isoformat(),
                    "open": 100,
                    "high": 102,
                    "low": 99,
                    "close": 100 + index,
                    "volume": 1000 + index,
                }
            )
    return rows


def test_forecast_edge_plan_reports_prior_failures_and_gaps(monkeypatch):
    import src.hackaithon_mvp.forecast_edge_planner as planner

    monkeypatch.setattr(
        planner,
        "discover_local_ohlcv_sources",
        lambda repo_root=".": {"candidate_file_count": 5, "preferred_file_count": 5, "ticker_count_estimate": 5},
    )
    monkeypatch.setattr(planner, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple(_bars()))

    result = build_forecast_edge_plan(repo_root=".")
    report = render_forecast_edge_plan_report(result)

    assert result["prior_failed_metrics"]["beats_random"] is False
    assert result["timestamp_panel_available"] is True
    assert "Forecast Edge Planner" in report
    assert "no_local_ohlcv_bars_discovered" not in result["data_gaps"]
