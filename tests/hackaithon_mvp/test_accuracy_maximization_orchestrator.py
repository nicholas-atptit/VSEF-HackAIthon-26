import json

from src.hackaithon_mvp.accuracy_maximization_orchestrator import (
    render_accuracy_maximization_report,
    run_accuracy_maximization_pipeline,
)


def _bars():
    rows = []
    for ticker in ("AAA", "BBB"):
        for index in range(85):
            close = 100 + index * 0.2 + (0.5 if ticker == "BBB" else 0.0)
            rows.append(
                {
                    "date": f"2025-05-{index + 1:03d}",
                    "ticker": ticker,
                    "open": close - 0.1,
                    "high": close + 0.3,
                    "low": close - 0.3,
                    "close": close,
                    "volume": 1000 + index,
                }
            )
    return rows


def _write_training_outputs(root):
    forecast_path = root / "forecast_actual_rows.jsonl"
    rows = []
    for index in range(40):
        actual = "up" if index % 2 == 0 else "down"
        predicted = "down" if actual == "up" else "up"
        rows.append(
            {
                "ticker": "AAA",
                "horizon": 20,
                "model_id": "m1",
                "model_family": "classification",
                "forecast_timestamp": f"2025-06-{index + 1:02d}",
                "target": "absolute_direction",
                "predicted_direction": predicted,
                "predicted_probability": 0.2 if actual == "up" else 0.8,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
            }
        )
    forecast_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    (root / "model_evidence_records.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "record_id": "generated_m1_absolute_h20",
                        "model_key": "logistic_l2",
                        "model_family": "classification",
                        "target": "absolute_direction",
                        "horizon": 20,
                        "execution_mode": "local_full_model_run",
                        "validation_rows": 12,
                        "train_rows": 28,
                        "claim_scope": "diagnostic_only",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "training_run_summary.json").write_text(json.dumps({"model_results": []}), encoding="utf-8")
    return rows


def test_accuracy_maximization_pipeline_scores_fixed_holdout_policy(tmp_path, monkeypatch):
    from src.hackaithon_mvp import accuracy_maximization_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "build_accuracy_maximization_plan", lambda repo_root=".": {"planner_status": "ready"})
    monkeypatch.setattr(orchestrator, "load_discovered_ohlcv_rows", lambda repo_root=".": tuple(_bars()))

    def fake_training(dataset_path, output_root, max_models=None, max_workers=1, timeout_seconds_per_model=120):
        root = tmp_path / ".tmp_accuracy_maximization"
        _write_training_outputs(root)
        return {
            "training_run_status": "completed",
            "attempted_model_specs": 1,
            "trained_model_specs": 1,
            "tuned_model_specs": 1,
            "model_results": [],
        }

    monkeypatch.setattr(orchestrator, "run_full_eligible_model_training", fake_training)
    monkeypatch.setattr(
        orchestrator,
        "materialize_engine_evidence_from_training_run",
        lambda run_root, evidence_root: {
            "materialization_status": "completed",
            "evidence_root": evidence_root,
            "forecast_row_count": 40,
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "run_engine_universe_with_generated_evidence",
        lambda evidence_root, output_root: {"completed_count": 1, "skipped_count": 0, "failed_count": 0},
    )

    result = run_accuracy_maximization_pipeline(
        output_root=str(tmp_path / ".tmp_accuracy_maximization"),
        max_models=1,
        max_workers=1,
    )
    report = render_accuracy_maximization_report(result)

    assert result["pipeline_status"] == "completed_with_accuracy_maximization"
    assert result["flip_rescue_applied"] is True
    assert result["final_holdout_metrics"]["global_balanced_accuracy"] == 1.0
    assert (tmp_path / ".tmp_accuracy_maximization" / "selected_policy_holdout_rows.jsonl").exists()
    assert "Accuracy Maximization" in report
