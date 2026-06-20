import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.end_to_end_demo import render_end_to_end_demo_report, run_end_to_end_demo


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


def test_demo_summary_has_no_forbidden_public_terms():
    _assert_no_forbidden_terms(run_end_to_end_demo(policy_demo="h40"))


def test_demo_report_has_no_forbidden_public_terms():
    _assert_no_forbidden_terms(render_end_to_end_demo_report(run_end_to_end_demo()))


def test_demo_cli_output_has_no_forbidden_public_terms():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.end_to_end_demo"],
        check=True,
        capture_output=True,
        text=True,
    )

    json.loads(completed.stdout)
    _assert_no_forbidden_terms(completed.stdout)


def test_readme_mentions_demo_without_forbidden_terms():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "CLI Demo Scenario / End-to-End Local Run" in readme
    _assert_no_forbidden_terms(readme)


def test_demo_source_has_no_runtime_integration_calls():
    source = Path("src/hackaithon_mvp/end_to_end_demo.py").read_text(encoding="utf-8").lower()

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
