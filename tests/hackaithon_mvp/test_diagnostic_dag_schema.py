import pytest

from src.hackaithon_mvp.diagnostic_dag.dag_schema import (
    DAGExecutionContext,
    DAGNodeSpec,
    REQUIRED_CLAIM_BOUNDARY,
)


def test_dag_context_normalizes_inputs_and_builds_deterministic_run_id():
    first = DAGExecutionContext(ticker="vcb", timeframe="1 ngày", horizon_steps=1)
    second = DAGExecutionContext(ticker="VCB", timeframe="1d", horizon_steps=1)

    assert first.ticker == "VCB"
    assert first.timeframe == "1d"
    assert first.run_id == second.run_id


def test_dag_context_rejects_non_positive_horizon():
    with pytest.raises(ValueError, match="horizon_steps must be positive"):
        DAGExecutionContext(ticker="VCB", timeframe="1d", horizon_steps=0)


def test_dag_node_spec_uses_required_claim_boundary_flags():
    node = DAGNodeSpec(
        node_id="demo_node",
        node_name="Demo Node",
        layer="demo",
        produces=("demo_output",),
    )

    assert node.claim_boundary == REQUIRED_CLAIM_BOUNDARY
    assert node.to_dict()["execution_mode"] == "static_local"


def test_dag_node_spec_rejects_missing_claim_boundary_flag():
    boundary = dict(REQUIRED_CLAIM_BOUNDARY)
    boundary["no_inference"] = False

    with pytest.raises(ValueError, match="claim_boundary.no_inference"):
        DAGNodeSpec(
            node_id="demo_node",
            node_name="Demo Node",
            layer="demo",
            claim_boundary=boundary,
        )
