from src.hackaithon_mvp import performance_rescue_orchestrator as rescue
from src.hackaithon_mvp.performance_rescue_orchestrator import (
    render_performance_rescue_report,
    run_performance_rescue_pipeline,
)


def _bars(tickers=("AAA", "VN30"), count=120):
    rows = []
    for ticker_index, ticker in enumerate(tickers):
        for index in range(count):
            close = 100 + ticker_index * 3 + index * 0.05 + (1 if index % 6 < 3 else -1) * 0.2
            rows.append(
                {
                    "date": f"2025-01-{index + 1:03d}",
                    "ticker": ticker,
                    "open": close - 0.05,
                    "high": close + 0.4,
                    "low": close - 0.4,
                    "close": close,
                    "volume": 1000 + index,
                }
            )
    return rows


def test_performance_rescue_pipeline_runs_bounded(monkeypatch, tmp_path):
    output_root = tmp_path / ".tmp_performance_rescue"
    monkeypatch.setattr(rescue, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple(_bars()))
    monkeypatch.setattr(
        rescue,
        "run_engine_universe_with_generated_evidence",
        lambda **kwargs: {
            "engine_universe_run_status": "completed_with_generated_evidence",
            "completed_count": 10,
            "skipped_count": 5,
            "failed_count": 0,
            "completed_improvement": -110,
            "skipped_reduction": 77725,
            "skip_reason_distribution": {"test_skip": 5},
        },
    )

    result = run_performance_rescue_pipeline(output_root=str(output_root), max_workers=1, max_models=1)
    report = render_performance_rescue_report(result)

    assert result["pipeline_status"] == "completed_partial_due_to_dependencies"
    assert result["training"]["attempted_model_specs"] == 1
    assert (output_root / "champion_forecast_actual_rows.jsonl").exists()
    assert "Performance Rescue Pipeline" in report
