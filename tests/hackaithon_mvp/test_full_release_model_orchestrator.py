from src.hackaithon_mvp import full_release_model_orchestrator as orchestrator
from src.hackaithon_mvp.full_release_model_orchestrator import (
    render_full_release_model_pipeline_report,
    run_full_release_model_pipeline,
)


def _bars(tickers=("AAA", "VN30"), count=180):
    rows = []
    for ticker_index, ticker in enumerate(tickers):
        for index in range(count):
            direction = 1 if index % 2 == 0 else -1
            close = 100 + ticker_index * 2 + index * 0.1 + direction * 0.5
            rows.append(
                {
                    "timestamp": f"2025-04-{index + 1:03d}",
                    "ticker": ticker,
                    "open": close - 0.1,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": 1000 + index,
                }
            )
    return rows


def _plan():
    return {
        "plan_status": "ready",
        "runnable_baseline_specs": [{"model_key": "majority_class"}],
        "blocked_specs_by_reason": {},
    }


def test_full_release_pipeline_runs_with_monkeypatched_local_bars(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "load_discovered_ohlcv_rows", lambda **_: tuple(_bars()))
    monkeypatch.setattr(orchestrator, "build_full_model_run_plan", lambda **_: _plan())

    result = run_full_release_model_pipeline(
        output_root=str(tmp_path / ".tmp_full_model_run"),
        max_models=2,
        max_workers=1,
    )
    report = render_full_release_model_pipeline_report(result)

    assert result["pipeline_status"] in {"completed_partial_due_to_dependencies", "completed_with_generated_evidence"}
    assert result["training"]["trained_model_specs"] >= 1
    assert result["engine_universe"]["completed_count"] > 0
    assert "Full Release Model Pipeline" in report


def test_full_release_pipeline_reports_data_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "load_discovered_ohlcv_rows", lambda **_: tuple())
    monkeypatch.setattr(orchestrator, "build_full_model_run_plan", lambda **_: {"plan_status": "blocked_by_data_unavailability"})

    result = run_full_release_model_pipeline(output_root=str(tmp_path / ".tmp_full_model_run"), max_models=1)

    assert result["pipeline_status"] == "blocked_by_data_unavailability"
    assert result["provider_fetch_used"] is False
    assert result["engine_universe"]["skip_reason_distribution"]["insufficient_local_supervised_rows"] == 77_850
