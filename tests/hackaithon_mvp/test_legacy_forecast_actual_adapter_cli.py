import json
import subprocess
import sys


def test_cli_evaluate_works_on_tiny_fixture(tmp_path):
    path = tmp_path / "legacy.csv"
    path.write_text(
        "\n".join(
            [
                "ticker,datetime,horizon,y_true,y_pred,model_group",
                "VCB,2025-01-02,1,1,1,classification",
                "VCB,2025-01-03,1,0,1,classification",
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.legacy_forecast_actual_adapter",
            "--input",
            str(path),
            "--timeframe",
            "1d",
            "--evaluate",
            "--top-k",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["conversion_summary"]["rows_total"] == 2
    assert output["evaluation"]["actual_data_status"] == "provided"
    assert output["evaluation"]["directional_accuracy"] == 0.5
    assert output["evaluation"]["top_k_summary"]["selected_rows"] == 1


def test_cli_default_prints_conversion_summary_only(tmp_path):
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps({"ticker": "VCB", "datetime": "2025-01-02", "horizon": 1, "y_true": 1, "y_pred": 1}) + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.legacy_forecast_actual_adapter",
            "--input",
            str(path),
            "--timeframe",
            "1d",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["conversion_summary"]["rows_total"] == 1
    assert "evaluation" not in output


def test_cli_write_creates_requested_file(tmp_path):
    input_path = tmp_path / "legacy.json"
    output_path = tmp_path / "converted" / "rows.jsonl"
    input_path.write_text(
        json.dumps([{"ticker": "VCB", "datetime": "2025-01-02", "horizon": 1, "y_true": 1, "y_pred": 1}]),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.legacy_forecast_actual_adapter",
            "--input",
            str(input_path),
            "--timeframe",
            "1d",
            "--format",
            "jsonl",
            "--write",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.exists()
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 1
