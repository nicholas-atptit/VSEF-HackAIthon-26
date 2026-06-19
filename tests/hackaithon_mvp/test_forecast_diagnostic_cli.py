import json
import subprocess
import sys


def test_forecast_diagnostic_cli_returns_json_and_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_diagnostic_engine",
            "--engine-id",
            "classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)
    assert output["engine_id"] == "classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055"
    assert output["forecast_diagnostic"] in {
        "positive_bias",
        "negative_bias",
        "neutral_or_uncertain",
        "insufficient_evidence",
        "exploratory_only",
    }
    assert output["human_review_required"] is True
