import json
import re
import subprocess
import sys


ACTION_OR_ATTRIBUTION_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "trading signal",
    "investment advice",
    "broker execution",
    "sponsored by",
    "sponsorship",
    "funding",
    "partnership",
    "endorsement",
    "client relationship",
    "approved by",
    "deployed for",
)


def _assert_neutral_public_output(text: str) -> None:
    lowered = text.lower()
    for term in ACTION_OR_ATTRIBUTION_TERMS:
        assert not re.search(rf"\b{re.escape(term)}\b", lowered), term


def test_orchestrator_cli_accepts_timeframe_and_keeps_neutral_output():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator",
            "--ticker",
            "VCB",
            "--sample-size",
            "20",
            "--timeframe",
            "1 ngày",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["timeframe"] == "1d"
    assert output["layer_1_quant_core"]["timeframe"] == "1d"
    _assert_neutral_public_output(completed.stdout)


def test_forecast_diagnostic_cli_accepts_timeframe_and_keeps_neutral_output():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_diagnostic_engine",
            "--engine-id",
            "classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055",
            "--timeframe",
            "1 ngày",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["timeframe"] == "1d"
    _assert_neutral_public_output(completed.stdout)


def test_invalid_timeframe_cli_fails_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator",
            "--ticker",
            "VCB",
            "--sample-size",
            "20",
            "--timeframe",
            "3m",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "unsupported timeframe" in completed.stderr.lower()
    assert "traceback" not in completed.stderr.lower()
