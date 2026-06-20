import csv
import json
import subprocess
import sys


def test_accuracy_optimizer_cli_works_with_tiny_legacy_fixture(tmp_path):
    path = tmp_path / "legacy.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "datetime", "horizon", "y_true", "y_pred"])
        writer.writeheader()
        for index in range(20):
            writer.writerow(
                {
                    "ticker": "AAA",
                    "datetime": f"2026-01-01T{index:02d}:00:00",
                    "horizon": "40",
                    "y_true": "1",
                    "y_pred": "1",
                }
            )
        for index in range(20, 40):
            writer.writerow(
                {
                    "ticker": "AAA",
                    "datetime": f"2026-01-01T{index:02d}:00:00",
                    "horizon": "40",
                    "y_true": "0",
                    "y_pred": "0",
                }
            )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.quant_core_accuracy_optimizer",
            "--input",
            str(path),
            "--legacy",
            "--timeframe",
            "1h",
            "--horizon-steps",
            "40",
            "--calibration-ratio",
            "0.5",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["baseline_validation"]["directional_accuracy"] == 1.0
    assert payload["candidate_count"] >= 4
    assert payload["best_policy_summary"]["policy_name"] == "baseline_pass_through"
    assert payload["claim_boundary"]["no_training"] is True
