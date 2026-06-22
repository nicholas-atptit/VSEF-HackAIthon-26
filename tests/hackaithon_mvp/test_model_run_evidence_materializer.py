import json

from src.hackaithon_mvp.full_eligible_model_trainer import run_full_eligible_model_training
from src.hackaithon_mvp.model_run_evidence_materializer import (
    materialize_engine_evidence_from_training_run,
    materialize_forecast_rows_from_training_run,
    materialize_model_diagnostics_from_training_run,
    render_model_run_evidence_report,
)


def _dataset_rows(count=180):
    rows = []
    for index in range(count):
        direction_up = index % 2 == 0
        future_return = 0.02 if direction_up else -0.02
        rows.append(
            {
                "ticker": "AAA",
                "timestamp": f"2025-02-{index + 1:03d}",
                "horizon": 1,
                "future_return": future_return,
                "future_direction": "up" if direction_up else "down",
                "market_relative_return": future_return,
                "market_relative_direction": "up" if direction_up else "down",
                "volatility_adjusted_future_return": future_return,
                "feature_lag_return_1": future_return,
                "feature_lag_return_2": 0.0,
                "feature_rolling_mean_return_5": future_return,
                "feature_rolling_volatility_5": 0.01,
                "feature_rolling_mean_return_10": future_return,
                "feature_rolling_volatility_10": 0.01,
                "feature_rolling_volume_mean_5": 1000,
                "feature_high_low_range": 0.01,
                "feature_close_open_return": 0.001,
                "feature_momentum_5": future_return,
                "feature_momentum_10": future_return,
                "feature_close_to_prev_close": future_return,
            }
        )
    return rows


def _run_training(tmp_path):
    output_root = tmp_path / ".tmp_full_model_run"
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text("\n".join(json.dumps(row) for row in _dataset_rows()) + "\n", encoding="utf-8")
    run_full_eligible_model_training(
        dataset_path=str(dataset_path),
        output_root=str(output_root),
        max_models=2,
        max_workers=1,
        timeout_seconds_per_model=30,
    )
    return output_root


def test_materialize_forecast_rows_and_diagnostics(tmp_path):
    run_root = _run_training(tmp_path)

    rows = materialize_forecast_rows_from_training_run(run_root=str(run_root))
    diagnostics = materialize_model_diagnostics_from_training_run(run_root=str(run_root))

    assert rows["forecast_row_count"] > 0
    assert diagnostics["model_diagnostic_count"] > 0


def test_materialize_engine_evidence_writes_expected_files(tmp_path):
    run_root = _run_training(tmp_path)
    evidence_root = run_root / "evidence"

    result = materialize_engine_evidence_from_training_run(run_root=str(run_root), evidence_root=str(evidence_root))
    report = render_model_run_evidence_report(result)

    assert result["static_evidence_record_count"] > 0
    assert result["dependency_result_count"] > 0
    assert (evidence_root / "static_evidence.json").exists()
    assert (evidence_root / "dependency_results.jsonl").exists()
    assert "Model Run Evidence Materialization" in report
