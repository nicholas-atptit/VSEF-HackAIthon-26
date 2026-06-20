import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.public_demo_readiness import (
    build_public_demo_readiness_summary,
    render_public_demo_readiness_report,
)


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


def _public_payload(summary: dict) -> dict:
    return {
        "readiness_status": summary["readiness_status"],
        "demo_command_count": summary["demo_command_count"],
        "default_commands_write_files": summary["default_commands_write_files"],
        "requires_live_data": summary["requires_live_data"],
        "requires_provider": summary["requires_provider"],
        "runs_training": summary["runs_training"],
        "runs_inference": summary["runs_inference"],
        "runs_benchmark": summary["runs_benchmark"],
        "submission_recommendation": summary["submission_recommendation"],
        "remaining_manual_items": summary["remaining_manual_items"],
        "non_claim": summary["non_claim"],
    }


def _assert_no_forbidden_terms(payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    lowered = text.lower()
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_public_readiness_summary_public_fields_have_no_forbidden_terms():
    _assert_no_forbidden_terms(_public_payload(build_public_demo_readiness_summary()))


def test_public_readiness_report_has_no_forbidden_terms():
    _assert_no_forbidden_terms(render_public_demo_readiness_report(build_public_demo_readiness_summary()))


def test_public_readiness_cli_report_has_no_forbidden_terms():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.public_demo_readiness", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    _assert_no_forbidden_terms(completed.stdout)


def test_readme_has_no_public_forbidden_terms():
    _assert_no_forbidden_terms(Path("README.md").read_text(encoding="utf-8"))


def test_readiness_source_has_no_runtime_integration_calls():
    source = Path("src/hackaithon_mvp/public_demo_readiness.py").read_text(encoding="utf-8").lower()

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
