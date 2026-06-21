import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.dag_forecast_output_verification import (
    render_dag_forecast_verification_table,
    run_dag_forecast_verification_cases,
)
from src.hackaithon_mvp.dashboard_artifact_export import (
    build_dashboard_artifact,
    render_dashboard_artifact_json,
)
from src.hackaithon_mvp.diagram_coverage_matrix import (
    build_diagram_coverage_matrix,
    render_diagram_coverage_report,
)
from src.hackaithon_mvp.diagram_demo_readiness import (
    build_diagram_demo_readiness_summary,
    render_diagram_demo_readiness_report,
)
from src.hackaithon_mvp.public_architecture_alignment import (
    build_public_architecture_alignment,
    render_public_architecture_alignment_report,
)


FORBIDDEN_PUBLIC_PATTERNS = (
    r"\b" + ("v" + "sef") + r"\b",
    r"\b" + ("viet" + "combank") + r"\b",
    r"\b" + ("viet" + "tel") + r"\b",
    r"\b" + ("q" + "ml") + r"\b",
    r"\bnon-" + ("q" + "ml") + r"\b",
    r"\bnon" + ("q" + "ml") + r"\b",
    r"\b" + ("b" + "uy") + r"\b",
    r"\b" + ("s" + "ell") + r"\b",
    r"\b" + ("h" + "old") + r"\b",
    r"\b" + ("tr" + "ading") + r"\b",
    r"\b" + ("financial" + " advice") + r"\b",
    r"\b" + ("investment" + " advice") + r"\b",
    r"\bfinancial decision\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\b" + ("sup" + "port") + r"(?:ed|s|ing)?\b",
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
    "benchmark_runner",
)
LEVEL_1_2_MODULES = (
    "src/hackaithon_mvp/dag_forecast_output_verification.py",
    "src/hackaithon_mvp/diagram_coverage_matrix.py",
    "src/hackaithon_mvp/public_architecture_alignment.py",
    "src/hackaithon_mvp/periodic_diagnostic_runner.py",
    "src/hackaithon_mvp/dashboard_artifact_export.py",
    "src/hackaithon_mvp/social_listening_contract.py",
    "src/hackaithon_mvp/feedback_loop_contract.py",
    "src/hackaithon_mvp/diagram_demo_readiness.py",
)


def _assert_no_forbidden_public_terms(text: str) -> None:
    lowered = text.lower()
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_level_1_2_reports_have_no_forbidden_public_terms():
    outputs = (
        render_dag_forecast_verification_table(run_dag_forecast_verification_cases()),
        render_diagram_coverage_report(build_diagram_coverage_matrix()),
        render_public_architecture_alignment_report(build_public_architecture_alignment()),
        render_dashboard_artifact_json(build_dashboard_artifact()),
        render_diagram_demo_readiness_report(build_diagram_demo_readiness_summary()),
    )

    for output in outputs:
        _assert_no_forbidden_public_terms(output)


def test_level_1_2_clis_exit_cleanly_and_public_outputs_are_safe():
    commands = (
        [sys.executable, "-m", "src.hackaithon_mvp.dag_forecast_output_verification", "--format", "report"],
        [sys.executable, "-m", "src.hackaithon_mvp.diagram_coverage_matrix", "--format", "report"],
        [sys.executable, "-m", "src.hackaithon_mvp.public_architecture_alignment", "--format", "report"],
        [sys.executable, "-m", "src.hackaithon_mvp.periodic_diagnostic_runner", "--once"],
        [sys.executable, "-m", "src.hackaithon_mvp.dashboard_artifact_export"],
        [sys.executable, "-m", "src.hackaithon_mvp.social_listening_contract"],
        [sys.executable, "-m", "src.hackaithon_mvp.feedback_loop_contract"],
        [sys.executable, "-m", "src.hackaithon_mvp.diagram_demo_readiness", "--format", "report"],
    )

    for command in commands:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        assert completed.stdout.strip()
        _assert_no_forbidden_public_terms(completed.stdout)


def test_level_1_2_json_outputs_parse_when_expected():
    commands = (
        [sys.executable, "-m", "src.hackaithon_mvp.dag_forecast_output_verification"],
        [sys.executable, "-m", "src.hackaithon_mvp.diagram_coverage_matrix"],
        [sys.executable, "-m", "src.hackaithon_mvp.public_architecture_alignment"],
        [sys.executable, "-m", "src.hackaithon_mvp.dashboard_artifact_export", "--format", "json"],
    )

    for command in commands:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        json.loads(completed.stdout)


def test_level_1_2_sources_have_no_runtime_integration_calls():
    source = "\n".join(Path(path).read_text(encoding="utf-8").lower() for path in LEVEL_1_2_MODULES)

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
