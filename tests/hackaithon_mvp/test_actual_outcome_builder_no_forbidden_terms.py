import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.actual_outcome_builder import build_actual_outcomes, render_actual_outcome_summary


FORBIDDEN_PUBLIC_PATTERNS = (
    r"\bvsef\b",
    r"\bvietcombank\b",
    r"\bviettel\b",
    r"\bqml\b",
    r"\bnon-qml\b",
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\btrading\b",
    r"\binvestment advice\b",
    r"\bfinancial advice\b",
    r"\bfinancial decision\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bapproval\b",
    r"\bclient relationship\b",
)
FORBIDDEN_RUNTIME_TERMS = (
    "requests.get",
    "provider.get",
    "provider_client",
    ".fit(",
    ".predict(",
    "train(",
    "infer(",
    "benchmark_runner",
)


def _assert_no_forbidden_terms(payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    lowered = text.lower()
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_actual_outcome_outputs_have_no_forbidden_public_terms():
    rows = build_actual_outcomes(
        (
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "prediction_timestamp": "2026-01-01T00:00:00+07:00",
                "horizon_steps": 1,
                "forecast_diagnostic": "positive_bias",
            },
        ),
        (
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "timestamp": "2026-01-01T00:00:00+07:00",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10,
                "volume": 100,
            },
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "timestamp": "2026-01-02T00:00:00+07:00",
                "open": 12,
                "high": 13,
                "low": 11,
                "close": 12,
                "volume": 100,
            },
        ),
    )

    _assert_no_forbidden_terms(render_actual_outcome_summary(rows))


def test_actual_outcome_cli_output_has_no_forbidden_public_terms(tmp_path):
    forecasts = tmp_path / "forecasts.jsonl"
    bars = tmp_path / "bars.jsonl"
    forecasts.write_text(
        json.dumps(
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "prediction_timestamp": "2026-01-01T00:00:00+07:00",
                "horizon_steps": 1,
                "forecast_diagnostic": "neutral_or_uncertain",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    bars.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "ticker": "VCB",
                    "timeframe": "1d",
                    "timestamp": "2026-01-01T00:00:00+07:00",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10,
                    "volume": 100,
                },
                {
                    "ticker": "VCB",
                    "timeframe": "1d",
                    "timestamp": "2026-01-02T00:00:00+07:00",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10,
                    "volume": 100,
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.actual_outcome_builder",
            "--forecasts",
            str(forecasts),
            "--bars",
            str(bars),
            "--evaluate",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    json.loads(completed.stdout)
    _assert_no_forbidden_terms(completed.stdout)


def test_readme_has_actual_outcome_step_without_stale_terms():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Actual Outcome Builder from Local Bars" in readme
    assert "Forecast-Actual-DAG Storage Loop" in readme
    assert "# VSEF HackAIthon 2026 MVP" not in readme
    _assert_no_forbidden_terms(readme)


def test_actual_outcome_builder_source_has_no_runtime_integration_calls():
    source = Path("src/hackaithon_mvp/actual_outcome_builder.py").read_text(encoding="utf-8").lower()

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
