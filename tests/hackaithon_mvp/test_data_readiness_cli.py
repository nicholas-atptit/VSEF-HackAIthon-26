import json
import re
import subprocess
import sys


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bclient relationship\b",
    r"\bprovider call\b",
)


def _run_cli(*extra_args):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.data_readiness_audit",
            "--cases-per-pair",
            "10000",
            *extra_args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed, json.loads(completed.stdout)


def _assert_no_forbidden_terms(text: str) -> None:
    lowered = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_data_readiness_cli_empty_store_exits_cleanly():
    completed, output = _run_cli()

    assert output["expected_prediction_cases"] == 5_400_000
    assert output["requirements_count"] == 540
    assert output["coverage_ratio"] == 0
    assert output["database_required"] is True
    _assert_no_forbidden_terms(completed.stdout)


def test_data_readiness_cli_demo_fill_reaches_ready_path():
    completed, output = _run_cli("--demo-fill-bars", "20000")

    assert output["expected_prediction_cases"] == 5_400_000
    assert output["ready_count"] == 540
    assert output["missing_count"] == 0
    assert output["coverage_ratio"] == 1
    _assert_no_forbidden_terms(completed.stdout)
