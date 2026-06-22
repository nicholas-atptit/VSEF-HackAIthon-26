import json

from src.hackaithon_mvp.full_eligible_model_trainer import (
    discover_trainable_model_specs,
    render_full_eligible_model_training_report,
    run_full_eligible_model_training,
    train_one_model_spec,
)


def _dataset_rows(count=180, horizon=1):
    rows = []
    for index in range(count):
        direction_up = index % 4 in {0, 1}
        future_return = 0.02 if direction_up else -0.015
        rows.append(
            {
                "ticker": "AAA" if index % 2 == 0 else "BBB",
                "timestamp": f"2025-01-{index + 1:03d}",
                "horizon": horizon,
                "future_return": future_return,
                "future_direction": "up" if direction_up else "down",
                "market_relative_return": future_return - 0.001,
                "market_relative_direction": "up" if future_return > 0.001 else "down",
                "volatility_adjusted_future_return": future_return,
                "feature_lag_return_1": 0.01 if direction_up else -0.01,
                "feature_lag_return_2": 0.0,
                "feature_rolling_mean_return_5": 0.01 if direction_up else -0.01,
                "feature_rolling_volatility_5": 0.02,
                "feature_rolling_mean_return_10": 0.0,
                "feature_rolling_volatility_10": 0.02,
                "feature_rolling_volume_mean_5": 1000 + index,
                "feature_high_low_range": 0.01,
                "feature_close_open_return": 0.001,
                "feature_momentum_5": 0.01 if direction_up else -0.01,
                "feature_momentum_10": 0.0,
                "feature_close_to_prev_close": 0.01 if direction_up else -0.01,
            }
        )
    return rows


def _write_dataset(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_discover_trainable_model_specs_lists_supported_groups():
    result = discover_trainable_model_specs()

    assert result["trainable_model_spec_count"] > 0
    assert "logistic_l2" in result["supported_model_keys"]


def test_train_one_model_spec_completes_with_majority_baseline(tmp_path):
    output_root = tmp_path / ".tmp_full_model_run"
    spec = {"model_key": "majority_class", "model_family": "baseline", "target": "absolute_direction", "horizon": 1}

    result = train_one_model_spec(spec, _dataset_rows(), output_root=str(output_root))

    assert result["training_status"] == "completed"
    assert result["forecast_rows_written"] > 0
    assert (output_root / "forecast_actual_rows.jsonl").exists()


def test_run_full_training_writes_summary_and_tuning_report(tmp_path):
    output_root = tmp_path / ".tmp_full_model_run"
    dataset_path = tmp_path / "dataset.jsonl"
    _write_dataset(dataset_path, _dataset_rows())

    result = run_full_eligible_model_training(
        dataset_path=str(dataset_path),
        output_root=str(output_root),
        max_models=2,
        max_workers=1,
        timeout_seconds_per_model=30,
    )
    report = render_full_eligible_model_training_report(result)

    assert result["attempted_model_specs"] == 2
    assert result["trained_model_specs"] >= 1
    assert (output_root / "training_run_summary.json").exists()
    assert (output_root / "tuning_report.json").exists()
    assert "Full Eligible Model Training" in report
