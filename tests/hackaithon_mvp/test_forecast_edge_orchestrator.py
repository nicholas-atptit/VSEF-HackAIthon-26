from datetime import date, timedelta

from src.hackaithon_mvp.forecast_edge_orchestrator import (
    STATUS_FOUND,
    render_forecast_edge_report,
    run_forecast_edge_pipeline,
)


def _forecast_rows(count=320):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "edge_model",
                "model_family": "classification",
                "horizon": 1,
                "forecast_timestamp": (start + timedelta(days=index)).isoformat(),
                "actual_timestamp": (start + timedelta(days=index + 1)).isoformat(),
                "predicted_direction": actual,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
            }
        )
    return rows


def test_forecast_edge_orchestrator_materializes_retained_evidence(tmp_path, monkeypatch):
    import src.hackaithon_mvp.forecast_edge_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "build_forecast_edge_plan", lambda repo_root=".": {"plan_status": "fixture"})
    monkeypatch.setattr(orchestrator, "run_optional_data_expansion", lambda output_root: {"data_expansion_status": "disabled_by_default"})
    monkeypatch.setattr(orchestrator, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple([{"ticker": "AAA", "timestamp": "2025-01-01", "open": 1, "high": 2, "low": 1, "close": 1, "volume": 1}]))
    monkeypatch.setattr(
        orchestrator,
        "build_clean_direction_targets",
        lambda bars, horizons, non_overlapping: {"target_status": "ready", "rows": [{"ticker": "AAA", "horizon": 1, "timestamp": "2025-01-01", "future_direction": "up", "feature_x": 1.0}] * 400, "retained_rows": 400},
    )
    monkeypatch.setattr(
        orchestrator,
        "build_forecast_edge_features",
        lambda bars: {"feature_status": "ready", "rows": [{"ticker": "AAA", "timestamp": "2025-01-01", "feature_x": 1.0}], "feature_blocks": ["technical"], "feature_columns": ["feature_x"]},
    )
    monkeypatch.setattr(
        orchestrator,
        "train_forecast_edge_models",
        lambda rows, horizons, max_models, max_workers, min_slice_rows: {
            "training_status": "completed",
            "clean_training_rows": len(rows),
            "attempted_model_specs": 1,
            "trained_model_specs": 1,
            "tuned_model_specs": 1,
            "model_results": [
                {
                    "slice_id": "AAA|h1|edge_model",
                    "ticker": "AAA",
                    "horizon": 1,
                    "model_id": "edge_model",
                    "holdout_rows": 320,
                    "minimum_holdout_rows": 300,
                    "validation_metrics": {"balanced_accuracy": 0.8, "mcc": 0.6},
                    "holdout_metrics": {"coverage_count": 320, "accuracy": 1.0, "balanced_accuracy": 1.0, "mcc": 1.0},
                    "holdout_baselines": {"random_50_50_baseline_accuracy": 0.5, "majority_class_baseline_accuracy": 0.5, "previous_direction_baseline_accuracy": 0.0},
                    "holdout_forecast_rows": _forecast_rows(),
                    "duplicate_key_severity": "none",
                    "overlap_severity": "none",
                    "leakage_warning": False,
                }
            ],
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "run_engine_universe_with_generated_evidence",
        lambda **kwargs: {"engine_universe_run_status": "completed_with_generated_evidence", "completed_count": 1, "skipped_count": 0, "failed_count": 0},
    )

    result = run_forecast_edge_pipeline(output_root=str(tmp_path / ".tmp_forecast_edge"), max_models=1, max_workers=1, min_slice_rows=300)
    report = render_forecast_edge_report(result)

    assert result["forecast_edge_status"] == STATUS_FOUND
    assert result["allowed_forecast_slices"] == 1
    assert result["retained_holdout_balanced_accuracy"] == 1.0
    assert (tmp_path / ".tmp_forecast_edge" / "retained_forecast_rows.jsonl").exists()
    assert "Forecast Edge Orchestrator" in report
