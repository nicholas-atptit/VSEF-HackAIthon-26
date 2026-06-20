import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_storage_bridge import (
    build_dag_artifact_records,
    build_dag_node_records,
    build_dag_run_record,
    load_static_context_from_storage,
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


def test_storage_bridge_outputs_have_no_forbidden_public_terms(tmp_path):
    result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
        storage_context=load_static_context_from_storage(
            storage_root=str(tmp_path),
            ticker="VCB",
            timeframe="1d",
            date="2026-01-01",
        ),
    )
    payload = {
        "run": build_dag_run_record(result),
        "nodes": build_dag_node_records(result),
        "artifacts": build_dag_artifact_records(result),
    }

    _assert_no_forbidden_terms(payload)


def test_dag_storage_cli_output_has_no_forbidden_public_terms(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_dag.dag_cli",
            "--ticker",
            "VCB",
            "--timeframe",
            "1 ngày",
            "--horizon-steps",
            "1",
            "--storage-root",
            str(tmp_path),
            "--load-storage-context",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    json.loads(completed.stdout)
    _assert_no_forbidden_terms(completed.stdout)


def test_readme_has_storage_to_dag_section_without_stale_terms():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Storage-to-DAG Runtime Integration" in readme
    assert "Actual Outcome Builder from Local Bars" in readme
    assert "# VSEF HackAIthon 2026 MVP" not in readme
    _assert_no_forbidden_terms(readme)


def test_dag_storage_sources_have_no_runtime_integration_calls():
    source_paths = (
        Path("src/hackaithon_mvp/diagnostic_dag/dag_storage_bridge.py"),
        Path("src/hackaithon_mvp/diagnostic_dag/dag_executor.py"),
        Path("src/hackaithon_mvp/diagnostic_dag/dag_cli.py"),
    )
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_paths)

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
