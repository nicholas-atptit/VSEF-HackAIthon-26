from src.hackaithon_mvp.accuracy_maximization_planner import (
    build_accuracy_maximization_plan,
    render_accuracy_maximization_plan_report,
)


def _bars():
    rows = []
    for ticker in ("AAA", "BBB"):
        for index in range(85):
            close = 100 + index * 0.1 + (0.2 if ticker == "BBB" else 0.0)
            rows.append(
                {
                    "date": f"2025-04-{index + 1:03d}",
                    "ticker": ticker,
                    "open": close - 0.1,
                    "high": close + 0.2,
                    "low": close - 0.2,
                    "close": close,
                    "volume": 1000 + index,
                }
            )
    return rows


def test_accuracy_maximization_plan_reports_local_readiness(monkeypatch):
    from src.hackaithon_mvp import accuracy_maximization_planner as planner

    monkeypatch.setattr(planner, "discover_local_ohlcv_sources", lambda repo_root=".": {"candidate_file_count": 2})
    monkeypatch.setattr(planner, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple(_bars()))
    result = build_accuracy_maximization_plan()
    report = render_accuracy_maximization_plan_report(result)

    assert result["planner_status"] == "ready"
    assert result["supervised_dataset_rows"] > 0
    assert result["recommended_horizons_to_prioritize"]
    assert "cross_sectional" in result["candidate_feature_blocks"]
    assert "Accuracy Maximization" in report
