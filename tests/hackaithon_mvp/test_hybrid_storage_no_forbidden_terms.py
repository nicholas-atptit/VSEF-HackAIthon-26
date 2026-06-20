import json
import re
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.hybrid_storage_architecture import (
    compare_storage_options,
    get_hybrid_storage_architecture,
    map_diagnostic_components_to_storage,
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


def _assert_no_forbidden_public_terms(text: str) -> None:
    lowered = text.lower()
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_readme_has_no_stale_public_wording():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "# VSEF HackAIthon 2026 MVP" not in readme
    assert "Forecast Diagnostic Engine | Next" not in readme
    assert "8-Layer Diagnostic Chain | Next" not in readme
    assert "GitHub HTTPS/SSH transport timeout" not in readme
    _assert_no_forbidden_public_terms(readme)


def test_hybrid_contract_outputs_have_no_forbidden_public_terms():
    payload = {
        "architecture": get_hybrid_storage_architecture(),
        "component_map": map_diagnostic_components_to_storage(),
        "options": compare_storage_options(),
    }

    _assert_no_forbidden_public_terms(json.dumps(payload, sort_keys=True))


def test_hybrid_cli_outputs_have_no_forbidden_public_terms():
    for section in ("architecture", "component-map", "options", "all"):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.hackaithon_mvp.hybrid_storage_architecture",
                "--section",
                section,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        json.loads(completed.stdout)
        _assert_no_forbidden_public_terms(completed.stdout)


def test_hybrid_storage_sources_have_no_runtime_integration_calls():
    source_paths = (
        Path("src/hackaithon_mvp/hybrid_storage_architecture.py"),
        Path("src/hackaithon_mvp/storage_design.py"),
        Path("src/hackaithon_mvp/data_readiness_audit.py"),
    )
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in source_paths)

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
