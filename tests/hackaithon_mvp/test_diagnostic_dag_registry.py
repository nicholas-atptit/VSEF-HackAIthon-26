from src.hackaithon_mvp.diagnostic_dag.dag_registry import (
    DEFAULT_DAG_NODE_IDS,
    build_default_diagnostic_dag,
    get_node_by_id,
    summarize_dag,
)


def test_default_dag_has_expected_nodes_in_registry_order():
    nodes = build_default_diagnostic_dag()

    assert tuple(node["node_id"] for node in nodes) == DEFAULT_DAG_NODE_IDS


def test_default_dag_summary_counts_nodes_edges_and_boundaries():
    summary = summarize_dag(build_default_diagnostic_dag())

    assert summary["node_count"] == 13
    assert summary["required_node_count"] == 12
    assert summary["optional_node_count"] == 1
    assert len(summary["edges"]) == 13
    assert summary["all_dependencies_registered"] is True
    assert all(summary["claim_boundary"].values())


def test_get_node_by_id_returns_node_copy():
    nodes = build_default_diagnostic_dag()
    node = get_node_by_id(nodes, "quant_core_policy_runtime")

    assert node["node_id"] == "quant_core_policy_runtime"
    assert node["execution_mode"] == "optional"
    assert node["is_required"] is False
