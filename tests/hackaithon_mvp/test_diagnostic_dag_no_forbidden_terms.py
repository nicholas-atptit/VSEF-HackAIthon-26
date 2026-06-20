import json
import re
from pathlib import Path

from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag, summarize_dag
from src.hackaithon_mvp.quant_core_policy_registry import get_demo_policy_h40_direction_only


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\bfinancial advice\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bdeployment\b",
    r"\bapproval\b",
    r"\bclient relationship\b",
)
FORBIDDEN_ENGINE_IMPORTS = ("airflow", "prefect", "dagster", "celery")


def _assert_no_forbidden_terms(payload) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, text) is None, pattern


def test_dag_outputs_have_no_forbidden_public_terms():
    nodes = build_default_diagnostic_dag()
    no_policy = execute_diagnostic_dag(nodes, {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1})
    h40_policy = execute_diagnostic_dag(
        nodes,
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
        policy=get_demo_policy_h40_direction_only(),
    )

    _assert_no_forbidden_terms({"summary": summarize_dag(nodes), "no_policy": no_policy, "h40_policy": h40_policy})


def test_dag_claim_boundary_blocks_disallowed_runtime_behaviors():
    result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
    )

    assert result["claim_boundary"]["no_live_data"] is True
    assert result["claim_boundary"]["no_provider_calls"] is True
    assert result["claim_boundary"]["no_training"] is True
    assert result["claim_boundary"]["no_inference"] is True
    assert result["claim_boundary"]["human_review_required"] is True


def test_dag_package_has_no_external_workflow_engine_dependency():
    dag_root = Path("src/hackaithon_mvp/diagnostic_dag")
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in dag_root.glob("*.py"))

    for name in FORBIDDEN_ENGINE_IMPORTS:
        assert name not in source
