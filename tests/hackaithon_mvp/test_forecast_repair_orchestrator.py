from datetime import date, timedelta

from src.hackaithon_mvp.forecast_repair_orchestrator import (
    STATUS_IMPROVED,
    render_forecast_repair_report,
    run_forecast_repair_pipeline,
)


def _rows(count=30):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        forecast_day = start + timedelta(days=index)
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "m1",
                "model_family": "classification",
                "horizon": 1,
                "forecast_timestamp": forecast_day.isoformat(),
                "actual_timestamp": (forecast_day + timedelta(days=1)).isoformat(),
                "predicted_direction": actual,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
                "deoverlap_step_index": index,
            }
        )
    return rows


def test_forecast_repair_pipeline_reuses_rows_and_materializes_retained_evidence(tmp_path, monkeypatch):
    import src.hackaithon_mvp.forecast_repair_orchestrator as orchestrator

    def fake_load_or_train(**kwargs):
        root = kwargs["root"]
        return {"dataset_status": "fixture"}, _rows(), {
            "training_run_status": "fixture",
            "forecast_actual_output": str(root / "forecast_actual_rows.jsonl"),
        }

    monkeypatch.setattr(orchestrator, "_load_or_train_rows", fake_load_or_train)
    monkeypatch.setattr(
        orchestrator,
        "materialize_engine_evidence_from_training_run",
        lambda **kwargs: {"materialization_status": "fixture"},
    )
    monkeypatch.setattr(
        orchestrator,
        "run_engine_universe_with_generated_evidence",
        lambda **kwargs: {
            "engine_universe_run_status": "completed_with_generated_evidence",
            "completed_count": 1,
            "skipped_count": 0,
            "failed_count": 0,
        },
    )

    result = run_forecast_repair_pipeline(
        output_root=str(tmp_path / ".tmp_forecast_repair"),
        max_workers=1,
        max_models=1,
        min_slice_rows=10,
    )
    report = render_forecast_repair_report(result)

    assert result["forecast_mode_status"] == STATUS_IMPROVED
    assert result["rows_before_repair"] == 30
    assert result["clean_rows_retained"] == 30
    assert result["allowed_forecast_slices"] == 1
    assert result["retained_balanced_accuracy"] == 1.0
    assert result["broad_performance_claim_allowed"] is True
    assert (tmp_path / ".tmp_forecast_repair" / "retained_forecast_rows.jsonl").exists()
    assert "Forecast Repair Orchestrator" in report
