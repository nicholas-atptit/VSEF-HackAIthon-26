from datetime import date, timedelta

from src.hackaithon_mvp.data_expanded_60pct_forecaster import (
    render_data_expanded_60pct_forecast_report,
    run_data_expanded_60pct_forecaster,
)


def _forecast_rows(count=650, correct_ratio=0.62):
    start = date(2026, 1, 1)
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
                "predicted_probability": 0.8 if predicted == "up" else 0.2,
                "actual_return": 0.01 if actual == "up" else -0.01,
            }
        )
    return rows


def _write_expanded_panel(path, count=700):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["ticker,timestamp,open,high,low,close,volume,adjusted_close,index_return\n"]
    for index in range(count):
        lines.append(
            f"AAA,2026-01-{index + 1:03d},1,2,1,{1 + index},100,{1 + index},0.001\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
    return path


def test_data_expanded_forecaster_blocks_when_no_training_data(tmp_path, monkeypatch):
    import src.hackaithon_mvp.data_expanded_60pct_forecaster as forecaster

    monkeypatch.setattr(
        forecaster,
        "train_forecast_edge_models",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fallback path should be blocked")),
    )

    result = run_data_expanded_60pct_forecaster(output_root=str(tmp_path / ".tmp_real_expanded_60pct"), max_models=1)
    report = render_data_expanded_60pct_forecast_report(result)

    assert result["forecast_release_status"] == "expanded_data_required_for_60pct_attempt"
    assert result["ohlcv_only_fallback_blocked"] is True
    assert result["evidence_materialization"]["materialization_status"] == "skipped_expanded_data_required"
    assert "Data-Expanded 60% Forecast Attempt" in report
    assert "OHLCV-only fallback was blocked" in report


def test_data_expanded_forecaster_materializes_only_when_gate_passes(tmp_path, monkeypatch):
    import src.hackaithon_mvp.data_expanded_60pct_forecaster as forecaster

    rows = _forecast_rows()
    expanded_input = _write_expanded_panel(tmp_path / "expanded_price_panel.csv")
    monkeypatch.setattr(
        forecaster,
        "load_discovered_ohlcv_rows",
        lambda repo_root=".": tuple(
            {"ticker": "AAA", "timestamp": f"2026-01-{index + 1:03d}", "open": 1, "high": 2, "low": 1, "close": 1 + index, "volume": 100}
            for index in range(700)
        ),
    )
    monkeypatch.setattr(
        forecaster,
        "build_clean_direction_targets",
        lambda bars, horizons, non_overlapping: {
            "rows": [
                {
                    "ticker": "AAA",
                    "horizon": 1,
                    "timestamp": f"2026-01-{index + 1:03d}",
                    "forecast_timestamp": f"2026-01-{index + 1:03d}",
                    "future_direction": "up" if index % 2 == 0 else "down",
                    "actual_direction": "up" if index % 2 == 0 else "down",
                    "non_overlapping_target": True,
                }
                for index in range(800)
            ],
            "rows_by_horizon": {"1": 800},
        },
    )
    monkeypatch.setattr(
        forecaster,
        "build_expanded_forecast_features",
        lambda bars: {
            "rows": [{"ticker": "AAA", "timestamp": f"2026-01-{index + 1:03d}", "feature_x": 1.0} for index in range(800)],
            "feature_blocks": ["returns"],
            "feature_columns": ["feature_x"],
        },
    )
    monkeypatch.setattr(
        forecaster,
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
                    "validation_metrics": {"accuracy": 0.7, "balanced_accuracy": 0.7, "mcc": 0.3},
                    "holdout_metrics": {"coverage_count": 650, "accuracy": 0.62, "balanced_accuracy": 0.62, "mcc": 0.24},
                    "holdout_baselines": {"random_50_50_baseline_accuracy": 0.5, "majority_class_baseline_accuracy": 0.51, "previous_direction_baseline_accuracy": 0.5},
                    "validation_forecast_rows": rows,
                    "holdout_forecast_rows": rows,
                    "duplicate_key_severity": "none",
                    "overlap_severity": "none",
                    "leakage_warning": False,
                }
            ],
        },
    )

    result = run_data_expanded_60pct_forecaster(
        output_root=str(tmp_path / ".tmp_real_expanded_60pct"),
        expanded_input=str(expanded_input),
        max_models=1,
        min_slice_rows=500,
    )

    assert result["selective_60pct_gate_passed"] is True
    assert result["real_expanded_data_available"] is True
    assert result["evidence_materialization"]["materialization_status"] == "completed"
    assert (tmp_path / ".tmp_real_expanded_60pct" / "evidence" / "forecast_actual_rows.jsonl").exists()


def test_data_expanded_forecaster_explicit_fallback_is_labeled(tmp_path, monkeypatch):
    import src.hackaithon_mvp.data_expanded_60pct_forecaster as forecaster

    monkeypatch.setattr(forecaster, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple())
    monkeypatch.setattr(
        forecaster,
        "build_clean_direction_targets",
        lambda bars, horizons, non_overlapping: {"rows": [], "rows_by_horizon": {}},
    )
    monkeypatch.setattr(
        forecaster,
        "build_expanded_forecast_features",
        lambda bars: {"rows": [], "feature_blocks": [], "feature_columns": []},
    )
    monkeypatch.setattr(
        forecaster,
        "select_narrow_forecast_targets",
        lambda *args, **kwargs: {
            "allowed_count": 0,
            "exploratory_count": 0,
            "rejected_count": 0,
            "allowed_target_candidates": [],
        },
    )
    monkeypatch.setattr(
        forecaster,
        "train_forecast_edge_models",
        lambda *args, **kwargs: {
            "training_status": "blocked_by_insufficient_data",
            "model_results": [],
            "attempted_model_specs": 0,
            "trained_model_specs": 0,
            "tuned_model_specs": 0,
        },
    )

    result = run_data_expanded_60pct_forecaster(
        output_root=str(tmp_path / ".tmp_real_expanded_60pct"),
        allow_ohlcv_fallback=True,
        max_models=1,
    )

    assert result["fallback_status"] == "fallback_only_not_expected_to_reach_60pct"
    assert result["ohlcv_only_fallback_blocked"] is False
