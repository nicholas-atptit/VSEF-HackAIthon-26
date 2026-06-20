import json
import subprocess
import sys

from forecast_actual_fixtures import forecast_actual_rows


def test_cli_no_input_exits_cleanly_and_reports_missing_actual_data():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.forecast_actual_evaluation"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["actual_data_status"] == "missing"
    assert output["directional_accuracy"] is None
    assert output["claim_boundary"]["no_live_data"] is True


def test_cli_with_fixture_input_returns_metrics(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(list(forecast_actual_rows())), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_actual_evaluation",
            "--input",
            str(path),
            "--top-k",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["actual_data_status"] == "provided"
    assert output["directional_accuracy"] == 0.5
    assert output["coverage_ratio"] == round(4 / 7, 6)
    assert output["abstention_ratio"] == round(3 / 7, 6)
    assert output["top_k_summary"]["selected_rows"] == 2


def test_cli_report_format_and_write_flag_write_summary_only(tmp_path):
    input_path = tmp_path / "rows.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in forecast_actual_rows()), encoding="utf-8")
    output_path = tmp_path / "outputs" / "evaluation.md"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_actual_evaluation",
            "--input",
            str(input_path),
            "--format",
            "report",
            "--write",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# HackAIthon MVP Forecast Actual Evaluation" in completed.stdout
    assert output_path.exists()
    assert "# HackAIthon MVP Forecast Actual Evaluation" in output_path.read_text(encoding="utf-8")
