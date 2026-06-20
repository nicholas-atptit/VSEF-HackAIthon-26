"""Default diagnostic DAG registry for the HackAIthon MVP."""

from __future__ import annotations

from typing import Any

from .dag_schema import DAGNodeSpec, NON_CLAIM_TEXT, claim_boundary


DEFAULT_DAG_NODE_IDS = (
    "static_evidence_loader",
    "engine_runtime",
    "forecast_diagnostic_engine",
    "quant_core_policy_runtime",
    "scenario_engine",
    "risk_governance_engine",
    "decision_lane_engine",
    "market_context_engine",
    "calibration_engine",
    "research_allocation_view",
    "phase_router",
    "evidence_packet",
    "diagnostic_report",
)


def _node(
    node_id: str,
    node_name: str,
    layer: str,
    *,
    depends_on: tuple[str, ...] = (),
    required_inputs: tuple[str, ...] = (),
    optional_inputs: tuple[str, ...] = (),
    produces: tuple[str, ...] = (),
    is_required: bool = True,
    execution_mode: str = "static_local",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return DAGNodeSpec(
        node_id=node_id,
        node_name=node_name,
        layer=layer,
        depends_on=depends_on,
        required_inputs=required_inputs,
        optional_inputs=optional_inputs,
        produces=produces,
        is_required=is_required,
        execution_mode=execution_mode,
        claim_boundary=claim_boundary(),
        metadata=metadata or {},
    ).to_dict()


def build_default_diagnostic_dag() -> tuple[dict, ...]:
    """Build the static/local diagnostic DAG registry."""

    return (
        _node(
            "static_evidence_loader",
            "Static Evidence Loader",
            "static_evidence",
            required_inputs=("ticker", "timeframe", "horizon_steps"),
            produces=("static_evidence_records", "selected_evidence_record"),
            metadata={"runtime_boundary": "static_local_only"},
        ),
        _node(
            "engine_runtime",
            "Engine Runtime",
            "engine_runtime",
            depends_on=("static_evidence_loader",),
            required_inputs=("selected_evidence_record",),
            produces=("engine_result",),
            metadata={"runtime_boundary": "static_engine_lookup_only"},
        ),
        _node(
            "forecast_diagnostic_engine",
            "Forecast Diagnostic Engine",
            "forecast_diagnostic",
            depends_on=("engine_runtime",),
            required_inputs=("engine_result",),
            optional_inputs=("selected_evidence_record",),
            produces=("forecast_diagnostic", "quant_core_output"),
            metadata={"runtime_boundary": "bounded_label_conversion_only"},
        ),
        _node(
            "quant_core_policy_runtime",
            "Quant Core Policy Runtime",
            "policy_runtime",
            depends_on=("forecast_diagnostic_engine",),
            required_inputs=("forecast_diagnostic",),
            optional_inputs=("policy",),
            produces=("quant_core_output", "policy_metadata"),
            is_required=False,
            execution_mode="optional",
            metadata={"runtime_boundary": "optional_registry_policy_metadata"},
        ),
        _node(
            "scenario_engine",
            "Scenario Engine",
            "diagnostic_chain_layer_2",
            depends_on=("forecast_diagnostic_engine", "quant_core_policy_runtime"),
            required_inputs=("quant_core_output",),
            produces=("scenario_output",),
        ),
        _node(
            "risk_governance_engine",
            "Risk Governance Engine",
            "diagnostic_chain_layer_3",
            depends_on=("scenario_engine",),
            required_inputs=("quant_core_output", "scenario_output"),
            produces=("risk_output",),
        ),
        _node(
            "decision_lane_engine",
            "Decision Lane Engine",
            "diagnostic_chain_layer_4",
            depends_on=("risk_governance_engine",),
            required_inputs=("quant_core_output", "scenario_output", "risk_output"),
            produces=("decision_output",),
        ),
        _node(
            "market_context_engine",
            "Market Context Engine",
            "diagnostic_chain_layer_5",
            depends_on=("decision_lane_engine",),
            required_inputs=("ticker",),
            produces=("market_context_output",),
            execution_mode="contract_only",
            metadata={"runtime_boundary": "static_context_placeholder_only"},
        ),
        _node(
            "calibration_engine",
            "Calibration Engine",
            "diagnostic_chain_layer_6",
            depends_on=("market_context_engine",),
            required_inputs=("quant_core_output", "scenario_output", "risk_output", "decision_output"),
            produces=("calibration_output",),
        ),
        _node(
            "research_allocation_view",
            "Research Allocation View",
            "diagnostic_chain_layer_7",
            depends_on=("calibration_engine",),
            required_inputs=("decision_output", "risk_output", "calibration_output"),
            produces=("allocation_output",),
        ),
        _node(
            "phase_router",
            "Phase Router",
            "diagnostic_chain_layer_8",
            depends_on=("research_allocation_view",),
            required_inputs=("decision_output", "risk_output", "allocation_output"),
            produces=("router_output", "chain_output"),
        ),
        _node(
            "evidence_packet",
            "Evidence Packet",
            "review_artifact",
            depends_on=("phase_router",),
            required_inputs=("chain_output",),
            optional_inputs=("policy_metadata",),
            produces=("evidence_packet",),
        ),
        _node(
            "diagnostic_report",
            "Diagnostic Report",
            "review_artifact",
            depends_on=("evidence_packet",),
            required_inputs=("evidence_packet",),
            optional_inputs=("policy_metadata",),
            produces=("diagnostic_report",),
        ),
    )


def get_node_by_id(nodes: tuple[dict, ...], node_id: str) -> dict:
    for node in nodes:
        if node.get("node_id") == node_id:
            return dict(node)
    raise KeyError(f"unknown DAG node_id: {node_id}")


def summarize_dag(nodes: tuple[dict, ...]) -> dict:
    node_ids = {str(node.get("node_id")) for node in nodes}
    edges = []
    layers: list[str] = []
    required_count = 0
    optional_count = 0
    boundaries: dict[str, bool] = claim_boundary()
    for node in nodes:
        if node.get("is_required", True):
            required_count += 1
        else:
            optional_count += 1
        layer = str(node.get("layer", ""))
        if layer and layer not in layers:
            layers.append(layer)
        for dependency in node.get("depends_on", []) or []:
            edges.append({"from": str(dependency), "to": str(node.get("node_id"))})
        boundary = node.get("claim_boundary", {})
        if isinstance(boundary, dict):
            for key in boundaries:
                boundaries[key] = boundaries[key] and boundary.get(key) is True
    return {
        "node_count": len(nodes),
        "required_node_count": required_count,
        "optional_node_count": optional_count,
        "layers": layers,
        "edges": edges,
        "claim_boundary": boundaries,
        "non_claim": NON_CLAIM_TEXT,
        "all_dependencies_registered": all(edge["from"] in node_ids and edge["to"] in node_ids for edge in edges),
    }
