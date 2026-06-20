import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.forecast_actual_dag_loop import run_forecast_actual_loop


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


def _write_jsonl(path: Path, rows: tuple[dict, ...]) -> Path:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return path


def _forecast_rows():
    return (
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "prediction_timestamp": "2026-01-01T00:00:00+07:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
        },
    )


def _bar_rows():
    return (
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
    )


def test_loop_output_has_no_forbidden_public_terms():
    result = run_forecast_actual_loop(forecast_rows=_forecast_rows(), bar_rows=_bar_rows())

    _assert_no_forbidden_terms(result)


def test_cli_output_has_no_forbidden_public_terms(tmp_path):
    forecasts = _write_jsonl(tmp_path / "forecasts.jsonl", _forecast_rows())
    bars = _write_jsonl(tmp_path / "bars.jsonl", _bar_rows())

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_actual_dag_loop",
            "--forecasts",
            str(forecasts),
            "--bars",
            str(bars),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    json.loads(completed.stdout)
    _assert_no_forbidden_terms(completed.stdout)


def test_loop_source_has_no_runtime_integration_calls():
    source = Path("src/hackaithon_mvp/forecast_actual_dag_loop.py").read_text(encoding="utf-8").lower()

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
