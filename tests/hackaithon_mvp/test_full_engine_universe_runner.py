import json

from src.hackaithon_mvp.full_eligible_model_trainer import run_full_eligible_model_training
from src.hackaithon_mvp.full_engine_universe_runner import (
    render_full_engine_universe_run_report,
    run_engine_universe_with_generated_evidence,
)
from src.hackaithon_mvp.model_run_evidence_materializer import materialize_engine_evidence_from_training_run


def _dataset_rows(count=180):
    rows = []
    for index in range(count):
        direction_up = index % 2 == 0
        future_return = 0.02 if direction_up else -0.02
        rows.append(
            {
                "ticker": "AAA",
                "timestamp": f"2025-03-{index + 1:03d}",
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


def _evidence_root(tmp_path):
    run_root = tmp_path / ".tmp_full_model_run"
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text("\n".join(json.dumps(row) for row in _dataset_rows()) + "\n", encoding="utf-8")
    run_full_eligible_model_training(
        dataset_path=str(dataset_path),
        output_root=str(run_root),
        max_models=2,
        max_workers=1,
        timeout_seconds_per_model=30,
    )
    materialize_engine_evidence_from_training_run(run_root=str(run_root), evidence_root=str(run_root / "evidence"))
    return run_root / "evidence", run_root / "engine_sweep"


def test_engine_universe_runner_completes_specs_with_generated_evidence(tmp_path):
    evidence_root, output_root = _evidence_root(tmp_path)

    result = run_engine_universe_with_generated_evidence(
        evidence_root=str(evidence_root),
        output_root=str(output_root),
        max_specs=2500,
    )

    assert result["total_specs_attempted"] == 2500
    assert result["completed_count"] > 0
    assert result["skip_reason_distribution"]
    assert (output_root / "engine_universe_generated_evidence_summary.json").exists()


def test_engine_universe_runner_report_renders(tmp_path):
    evidence_root, output_root = _evidence_root(tmp_path)

    result = run_engine_universe_with_generated_evidence(
        evidence_root=str(evidence_root),
        output_root=str(output_root),
        max_specs=100,
    )
    report = render_full_engine_universe_run_report(result)

    assert "Full Engine Universe Run With Generated Evidence" in report
    assert "No metrics are fabricated" in report
