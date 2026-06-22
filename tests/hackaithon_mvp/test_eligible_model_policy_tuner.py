import json
import re
import subprocess
import sys

from src.hackaithon_mvp.eligible_model_policy_tuner import (
    render_eligible_model_tuning_report,
    temporal_train_validation_split,
    tune_all_eligible_models,
    tune_threshold_for_model,
)


def _eligible_rows(count=12, *, model_id="model-a", horizon=1, probability=True):
    rows = []
    for index in range(count):
        actual_up = index % 2 == 0
        row = {
            "ticker": "AAA",
            "model_id": model_id,
            "model_family": "classification",
            "horizon": horizon,
            "forecast_timestamp": f"2026-01-{index + 1:02d}T09:00:00",
            "actual_direction": "up" if actual_up else "down",
            "predicted_direction": "up" if actual_up else "down",
        }
        if probability:
            row["predicted_probability"] = 0.56 if actual_up else 0.44
        rows.append(row)
    return rows


def test_temporal_split_uses_late_rows_for_validation():
    split = temporal_train_validation_split(_eligible_rows(10), validation_fraction=0.3)

    assert split["split_status"] == "temporal_split_ready"
    assert len(split["train_rows"]) == 7
    assert len(split["validation_rows"]) == 3
    assert split["validation_rows"][0]["forecast_timestamp"] == "2026-01-08T09:00:00"


def test_tune_threshold_for_model_reports_pre_and_post_validation_metrics():
    result = tune_threshold_for_model(_eligible_rows(12))

    assert result["tuning_status"] == "tuned"
    assert 0.45 <= result["selected_threshold"] <= 0.55
    assert result["pre_tune_validation"]["balanced_accuracy"] is not None
    assert result["post_tune_validation"]["balanced_accuracy"] is not None
    assert result["training_ran"] is False


def test_tune_all_eligible_models_tunes_each_eligible_model_horizon():
    rows = _eligible_rows(12, model_id="model-a", horizon=1) + _eligible_rows(12, model_id="model-b", horizon=5)

    result = tune_all_eligible_models(rows)

    assert result["tuning_status"] == "completed"
    assert result["eligible_model_count"] == 2
    assert result["skipped_model_count"] == 0
    assert result["tuning_ran"] is True


def test_ineligible_models_are_skipped_with_reasons():
    result = tune_all_eligible_models(_eligible_rows(12, probability=False))

    assert result["tuning_status"] == "no_eligible_models"
    assert result["skipped_models"][0]["skip_reason"] == "missing_probability_scores"


def test_tuner_cli_requires_explicit_tmp_output(tmp_path):
    input_path = tmp_path / "forecast_actual_rows.jsonl"
    input_path.write_text(
        "\n".join(json.dumps(row) for row in _eligible_rows(12)) + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / ".tmp_tuning_report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.eligible_model_policy_tuner",
            "--input",
            str(input_path),
            "--write-report",
            str(output_path),
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["tuning_status"] == "completed"
    assert "Eligible Model Policy Tuning" in completed.stdout


def test_tuner_cli_accepts_full_model_run_tmp_output(tmp_path):
    input_path = tmp_path / "forecast_actual_rows.jsonl"
    input_path.write_text(
        "\n".join(json.dumps(row) for row in _eligible_rows(12)) + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / ".tmp_full_model_run"
    output_root.mkdir()
    output_path = output_root / "tuning_report.json"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.eligible_model_policy_tuner",
            "--input",
            str(input_path),
            "--write-report",
            str(output_path),
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["tuning_status"] == "completed"


def test_tuning_report_has_no_market_action_labels():
    report = render_eligible_model_tuning_report(tune_all_eligible_models(_eligible_rows(12))).lower()

    for forbidden in ("buy", "sell", "hold"):
        assert re.search(rf"\b{forbidden}\b", report) is None
