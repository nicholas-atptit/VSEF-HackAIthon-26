from datetime import date, timedelta

from src.hackaithon_mvp.forecast_60pct_edge_search import render_60pct_edge_search_report, run_60pct_edge_search


def _forecast_rows(count=650, correct_ratio=0.62):
    start = date(2025, 1, 1)
    cutoff = int(count * correct_ratio)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        predicted = actual if index < cutoff else ("down" if actual == "up" else "up")
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "m1",
                "model_family": "classification",
                "horizon": 1,
                "forecast_timestamp": (start + timedelta(days=index)).isoformat(),
                "actual_timestamp": (start + timedelta(days=index + 1)).isoformat(),
                "predicted_direction": predicted,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
            }
        )
    return rows


def test_60pct_edge_search_blocks_when_gate_fails(tmp_path, monkeypatch):
    import src.hackaithon_mvp.forecast_60pct_edge_search as search

    monkeypatch.setattr(search, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple())
    monkeypatch.setattr(search, "build_clean_direction_targets", lambda bars, horizons, non_overlapping: {"rows": [], "dropped_duplicate_keys": 0, "dropped_overlapping_windows": 0})
    monkeypatch.setattr(search, "build_forecast_edge_features", lambda bars: {"rows": [], "feature_blocks": [], "feature_columns": []})
    monkeypatch.setattr(search, "train_forecast_edge_models", lambda *args, **kwargs: {"training_status": "blocked_by_insufficient_data", "model_results": [], "attempted_model_specs": 0, "trained_model_specs": 0, "tuned_model_specs": 0})

    result = run_60pct_edge_search(output_root=str(tmp_path / ".tmp_60pct_gate"), max_models=1)
    report = render_60pct_edge_search_report(result)

    assert result["forecast_release_status"] == "forecast_release_blocked_insufficient_rows"
    assert result["evidence_materialization"]["materialization_status"] == "skipped_gate_not_passed"
    assert "60% Forecast Edge Search" in report


def test_60pct_edge_search_materializes_only_after_gate_pass(tmp_path, monkeypatch):
    import src.hackaithon_mvp.forecast_60pct_edge_search as search

    rows = _forecast_rows()
    monkeypatch.setattr(search, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple([{"ticker": "AAA", "timestamp": "2025-01-01", "open": 1, "high": 2, "low": 1, "close": 1, "volume": 1}]))
    monkeypatch.setattr(search, "build_clean_direction_targets", lambda bars, horizons, non_overlapping: {"rows": [{"ticker": "AAA", "horizon": 1, "timestamp": "2025-01-01", "future_direction": "up"}] * 800, "dropped_duplicate_keys": 0, "dropped_overlapping_windows": 0})
    monkeypatch.setattr(search, "build_forecast_edge_features", lambda bars: {"rows": [{"ticker": "AAA", "timestamp": "2025-01-01", "feature_x": 1.0}], "feature_blocks": ["technical"], "feature_columns": ["feature_x"]})
    monkeypatch.setattr(
            search,
            "train_forecast_edge_models",
            lambda *args, **kwargs: {
                "training_status": "completed",
            "attempted_model_specs": 1,
            "trained_model_specs": 1,
            "tuned_model_specs": 1,
            "model_results": [
                {
                    "training_status": "completed",
                    "scope": "global_horizon",
                    "ticker": "GLOBAL",
                    "horizon": 1,
                    "model_id": "m1",
                    "holdout_rows": 650,
                    "minimum_holdout_rows": 300,
                    "validation_metrics": {"balanced_accuracy": 0.7, "mcc": 0.2},
                    "holdout_metrics": {"coverage_count": 650, "accuracy": 0.62, "balanced_accuracy": 0.62, "mcc": 0.24},
                    "holdout_baselines": {"random_50_50_baseline_accuracy": 0.5, "majority_class_baseline_accuracy": 0.51, "previous_direction_baseline_accuracy": 0.5},
                    "holdout_forecast_rows": rows,
                    "duplicate_key_severity": "none",
                    "overlap_severity": "none",
                    "leakage_warning": False,
                }
            ],
        },
    )

    result = run_60pct_edge_search(output_root=str(tmp_path / ".tmp_60pct_gate"), max_models=1)

    assert result["selective_60pct_gate_passed"] is True
    assert result["evidence_materialization"]["materialization_status"] == "completed"
    assert (tmp_path / ".tmp_60pct_gate" / "evidence" / "forecast_actual_rows.jsonl").exists()
