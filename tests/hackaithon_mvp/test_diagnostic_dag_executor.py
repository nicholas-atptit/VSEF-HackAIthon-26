from src.hackaithon_mvp.diagnostic_dag import dag_executor
from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag


def _context():
    return {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1}


def _statuses(result):
    return {node["node_id"]: node["status"] for node in result["node_results"]}


def test_dag_execution_completes_without_policy():
    result = execute_diagnostic_dag(build_default_diagnostic_dag(), _context())

    assert result["dag_valid"] is True
    assert result["execution_status"] == "completed_with_warnings"
    assert result["ticker"] == "VCB"
    assert result["timeframe"] == "1d"
    assert result["final_state"]["quant_core_output"]["policy_runtime_status"] == "policy_not_applied"
    assert result["final_state"]["evidence_packet"]["ticker"] == "VCB"
    assert result["final_state"]["diagnostic_report"]["human_review_required"] is True


def test_required_node_failure_stops_execution_safely(monkeypatch):
    def fail_required(state, policy):
        raise RuntimeError("required fixture failure")

    monkeypatch.setitem(dag_executor.HANDLERS, "engine_runtime", fail_required)

    result = execute_diagnostic_dag(build_default_diagnostic_dag(), _context())

    assert result["execution_status"] == "failed"
    assert [node["node_id"] for node in result["node_results"]] == ["static_evidence_loader", "engine_runtime"]
    assert result["node_results"][-1]["error"] == "required fixture failure"


def test_optional_node_failure_continues_with_warning(monkeypatch):
    def fail_optional(state, policy):
        raise RuntimeError("optional fixture failure")

    monkeypatch.setitem(dag_executor.HANDLERS, "quant_core_policy_runtime", fail_optional)

    result = execute_diagnostic_dag(build_default_diagnostic_dag(), _context())
    statuses = _statuses(result)

    assert result["execution_status"] == "completed_with_warnings"
    assert statuses["quant_core_policy_runtime"] == "failed"
    assert statuses["diagnostic_report"] == "completed"
    assert any("optional fixture failure" in item["error"] for item in result["audit_trail"] if item["error"])


def test_executor_rejects_invalid_dag_before_running():
    nodes = tuple(
        {**node, "depends_on": ["missing_dependency"]} if node["node_id"] == "engine_runtime" else node
        for node in build_default_diagnostic_dag()
    )

    result = execute_diagnostic_dag(nodes, _context())

    assert result["dag_valid"] is False
    assert result["execution_status"] == "failed"
    assert "validation_errors" in result["final_state"]
