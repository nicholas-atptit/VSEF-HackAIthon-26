import csv
import json
import subprocess
import sys


def test_selector_summary_cli_works_with_tiny_legacy_fixture(tmp_path):
    path = tmp_path / "legacy.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ticker", "datetime", "horizon", "y_true", "y_pred", "y_score_or_probability"],
        )
        writer.writeheader()
        for index in range(15):
            writer.writerow(
                {
                    "ticker": "AAA",
                    "datetime": f"2026-01-01T{index:02d}:00:00",
                    "horizon": "40",
                    "y_true": "1",
                    "y_pred": "1",
                    "y_score_or_probability": str(index / 100),
                }
            )
        for index in range(15, 30):
            writer.writerow(
                {
                    "ticker": "AAA",
                    "datetime": f"2026-01-01T{index:02d}:00:00",
                    "horizon": "40",
                    "y_true": "0",
                    "y_pred": "0",
                    "y_score_or_probability": str(index / 100),
                }
            )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.quant_core_selector_summary",
            "--input",
            str(path),
            "--legacy",
            "--timeframe",
            "1h",
            "--horizon-steps",
            "40",
            "--min-sample-count",
            "30",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["rows_total"] == 30
    assert payload["global_accuracy"] == 1.0
    assert payload["strong_group_count"] == 1
    assert payload["recommended_quant_core_policy"]["use_abstention_for_weak_slices"] is True
    assert payload["score_calibration"]["eligible_rows"] == 30
