import pytest

from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_schema import claim_boundary
from src.hackaithon_mvp.diagnostic_dag.dag_validator import detect_cycles, topological_sort, validate_dag


def _node(node_id, depends_on=()):
    return {
        "node_id": node_id,
        "node_name": node_id.replace("_", " ").title(),
        "layer": "test",
        "depends_on": list(depends_on),
        "required_inputs": [],
        "optional_inputs": [],
        "produces": [],
        "is_required": True,
        "execution_mode": "static_local",
        "claim_boundary": claim_boundary(),
        "metadata": {},
    }


def test_default_dag_dependencies_are_valid_and_order_is_deterministic():
    nodes = build_default_diagnostic_dag()
    validation = validate_dag(nodes)

    assert validation["is_valid"] is True
    assert tuple(validation["topological_order"]) == topological_sort(nodes)
    assert tuple(validation["topological_order"]) == tuple(node["node_id"] for node in nodes)


def test_cycle_detection_reports_cycle():
    nodes = (_node("a", ("c",)), _node("b", ("a",)), _node("c", ("b",)))

    cycle = detect_cycles(nodes)

    assert cycle["has_cycle"] is True
    assert validate_dag(nodes)["is_valid"] is False


def test_duplicate_node_ids_are_rejected():
    validation = validate_dag((_node("a"), _node("a")))

    assert validation["is_valid"] is False
    assert any("duplicate node IDs" in error for error in validation["errors"])


def test_missing_dependencies_are_rejected():
    validation = validate_dag((_node("a", ("missing",)),))

    assert validation["is_valid"] is False
    assert any("missing dependency missing" in error for error in validation["errors"])


def test_topological_sort_raises_for_invalid_graph():
    with pytest.raises(ValueError, match="missing dependencies"):
        topological_sort((_node("a", ("missing",)),))
