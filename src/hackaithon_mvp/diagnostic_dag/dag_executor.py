"""Static/local diagnostic DAG executor."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from src.hackaithon_mvp.diagnostic_chain.calibration_engine import run_calibration
from src.hackaithon_mvp.diagnostic_chain.decision_lane_engine import run_decision_lane
from src.hackaithon_mvp.diagnostic_chain.market_context_engine import run_market_context
from src.hackaithon_mvp.diagnostic_chain.phase_router import run_phase_router
from src.hackaithon_mvp.diagnostic_chain.portfolio_diagnostic_allocator import run_portfolio_diagnostic_allocator
from src.hackaithon_mvp.diagnostic_chain.risk_governance_engine import run_risk_governance
from src.hackaithon_mvp.diagnostic_chain.scenario_engine import run_scenario_engine
from src.hackaithon_mvp.diagnostic_report import render_diagnostic_report
from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_runtime.engine_result import EngineResult
from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine
from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec
from src.hackaithon_mvp.evidence_packet import build_evidence_packet
from src.hackaithon_mvp.forecast_diagnostic_engine import run_forecast_diagnostic
from src.hackaithon_mvp.quant_core_policy_runtime import apply_registered_policy_to_forecast
from src.hackaithon_mvp.static_evidence_loader import load_static_evidence
from src.hackaithon_mvp.timeframe_schema import timeframe_unit

from .dag_schema import (
    DAGExecutionContext,
    DAGExecutionResult,
    DAGNodeResult,
    NON_CLAIM_TEXT,
    assert_no_forbidden_public_terms,
    claim_boundary,
)
from .dag_validator import topological_sort, validate_dag


Handler = Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]]
POLICY_FIELDS = (
    "policy_id",
    "policy_name",
    "policy_runtime_status",
    "pre_policy_forecast_diagnostic",
    "policy_validation_accuracy",
    "policy_validation_balanced_accuracy",
    "policy_validation_coverage",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node_success(outputs: dict[str, Any] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {"outputs": outputs or {}, "warnings": warnings or []}


def _node_failure(message: str) -> dict[str, Any]:
    raise RuntimeError(message)


def _matches_record(spec: EngineSpec, record: dict[str, Any]) -> bool:
    return (
        record.get("model_key") == spec.model_key
        and record.get("target") == spec.target
        and int(record.get("horizon", -1)) == spec.horizon
    )


def _matching_spec(record: dict[str, Any], horizon_steps: int) -> EngineSpec:
    model_key = str(record.get("model_key", "logistic_l2"))
    target = str(record.get("target", "absolute_direction"))
    record_horizon = int(record.get("horizon", horizon_steps))
    for spec in generate_baseline_catalog():
        if spec.model_key == model_key and spec.target == target and spec.horizon == record_horizon:
            return EngineSpec(
                **{
                    **spec.to_dict(),
                    "dependencies": tuple(spec.dependencies),
                    "timeframe": None,
                    "metadata": {**spec.metadata, "timeframe": record.get("timeframe")},
                }
            )
    return EngineSpec(
        engine_id=f"classification.logistic_l2.absolute_direction.h{record_horizon}.feature_set_c.threshold_055",
        engine_type="baseline",
        model_key=model_key,
        model_family=str(record.get("model_family", "classification")),
        target=target,
        horizon=record_horizon,
        feature_set="feature_set_c",
        policy="threshold_055",
        split_policy="static_mvp_split",
        run_mode="static_evidence_mvp",
        claim_scope="diagnostic_only",
        metadata={"timeframe": record.get("timeframe")},
    )


def _fallback_spec(context: DAGExecutionContext) -> EngineSpec:
    horizon = int(context.horizon_steps)
    return EngineSpec(
        engine_id=f"classification.logistic_l2.absolute_direction.h{horizon}.feature_set_c.threshold_055",
        engine_type="baseline",
        model_key="logistic_l2",
        model_family="classification",
        target="absolute_direction",
        horizon=horizon,
        feature_set="feature_set_c",
        policy="threshold_055",
        split_policy="static_mvp_split",
        run_mode="static_evidence_mvp",
        claim_scope="diagnostic_only",
        metadata={"timeframe": context.timeframe},
    )


def _policy_metadata(source: dict[str, Any]) -> dict[str, Any]:
    return {field: source[field] for field in POLICY_FIELDS if field in source}


def _forecast_counts(label: str) -> dict[str, int]:
    counts = Counter(
        {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "insufficient": 0,
            "exploratory": 0,
        }
    )
    mapping = {
        "positive_bias": "positive",
        "negative_bias": "negative",
        "neutral_or_uncertain": "neutral",
        "insufficient_evidence": "insufficient",
        "exploratory_only": "exploratory",
    }
    counts[mapping.get(label, "insufficient")] += 1
    return dict(counts)


def _quant_core_from_forecast(context: DAGExecutionContext, diagnostic: dict[str, Any], result: dict[str, Any]) -> dict:
    label = str(diagnostic.get("forecast_diagnostic", "insufficient_evidence"))
    status = str(result.get("status", "skipped_missing_evidence"))
    completed_count = 1 if status == "completed" else 0
    return {
        "ticker": context.ticker,
        "timeframe": context.timeframe,
        "timeframe_unit": timeframe_unit(context.timeframe),
        "quant_signal": label,
        "consensus_strength": 1.0 if completed_count else 0.0,
        "engine_count_checked": 1,
        "completed_count": completed_count,
        "skipped_missing_evidence_count": 0 if completed_count else 1,
        "forecast_diagnostic_engine_enabled": True,
        "forecast_diagnostic_counts": _forecast_counts(label),
        "forecast_diagnostic_sample": [
            {
                "engine_id": diagnostic.get("engine_id"),
                "forecast_diagnostic": label,
                "baseline_status": diagnostic.get("baseline_status"),
                "evidence_status": diagnostic.get("evidence_status"),
                "confidence": diagnostic.get("confidence"),
                "timeframe": context.timeframe,
            }
        ],
        "policy_runtime_status": "policy_not_applied",
        "warnings": [
            "static local sample evidence only",
            "provider access disabled",
            "model training disabled",
            "model inference disabled",
            "benchmark rerun disabled",
        ],
        "non_claim": NON_CLAIM_TEXT,
    }


def _compact_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine_id": result.get("engine_id"),
        "status": result.get("status"),
        "diagnostic_label": result.get("diagnostic_label"),
        "confidence": result.get("confidence"),
        "claim_scope": result.get("claim_scope"),
        "timeframe": result.get("timeframe") or result.get("metadata", {}).get("timeframe"),
    }


def _compact_forecast_payload(diagnostic: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine_id": diagnostic.get("engine_id"),
        "forecast_diagnostic": diagnostic.get("forecast_diagnostic"),
        "confidence": diagnostic.get("confidence"),
        "baseline_status": diagnostic.get("baseline_status"),
        "evidence_status": diagnostic.get("evidence_status"),
        "timeframe": diagnostic.get("timeframe"),
    }


def _compact_chain_output(state: dict[str, Any]) -> dict[str, Any]:
    chain_output = state["chain_output"]
    quant = chain_output.get("layer_1_quant_core", {})
    return {
        "ticker": chain_output.get("ticker"),
        "timeframe": chain_output.get("timeframe"),
        "layer_1_quant_core": {
            "quant_signal": quant.get("quant_signal"),
            "consensus_strength": quant.get("consensus_strength"),
            "engine_count_checked": quant.get("engine_count_checked"),
            "completed_count": quant.get("completed_count"),
            "skipped_missing_evidence_count": quant.get("skipped_missing_evidence_count"),
            "forecast_diagnostic_counts": quant.get("forecast_diagnostic_counts"),
            **_policy_metadata(quant),
        },
        "layer_2_scenario": {
            "scenario": state.get("scenario_output", {}).get("scenario"),
            "scenario_confidence": state.get("scenario_output", {}).get("scenario_confidence"),
        },
        "layer_3_risk_governance": {
            "risk_level": state.get("risk_output", {}).get("risk_level"),
            "risk_flags": state.get("risk_output", {}).get("risk_flags", []),
        },
        "layer_4_decision_lane": {
            "decision_lane": state.get("decision_output", {}).get("decision_lane"),
            "human_review_required": True,
        },
        "layer_5_market_context": {
            "market_context_status": state.get("market_context_output", {}).get("market_context_status"),
            "live_context_enabled": state.get("market_context_output", {}).get("live_context_enabled"),
        },
        "layer_6_calibration": {
            "calibrated_confidence": state.get("calibration_output", {}).get("calibrated_confidence"),
            "calibration_policy": state.get("calibration_output", {}).get("calibration_policy"),
            "fine_tuning_performed": state.get("calibration_output", {}).get("fine_tuning_performed"),
        },
        "layer_7_portfolio_diagnostic_allocator": {
            "allocation_view": state.get("allocation_output", {}).get("allocation_view"),
            "allocation_is_advisory": state.get("allocation_output", {}).get("allocation_is_advisory"),
        },
        "layer_8_phase_router": {
            "route": state.get("router_output", {}).get("route"),
            "dashboard_status": state.get("router_output", {}).get("dashboard_status"),
            "human_review_required": True,
        },
        "non_claim": NON_CLAIM_TEXT,
    }


def _compact_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": packet.get("run_id"),
        "ticker": packet.get("ticker"),
        "timeframe": packet.get("timeframe"),
        "run_mode": packet.get("run_mode"),
        "engine_universe_summary": packet.get("engine_universe_summary", {}),
        "forecast_diagnostic_summary": packet.get("forecast_diagnostic_summary", {}),
        "policy_metadata": packet.get("policy_metadata", {}),
        "chain_summary": packet.get("chain_summary", {}),
        "risk_summary": {
            "risk_level": packet.get("risk_summary", {}).get("risk_level"),
            "risk_flags": packet.get("risk_summary", {}).get("risk_flags", []),
        },
        "routing_summary": packet.get("routing_summary", {}),
        "human_review_required": True,
        "non_claim": NON_CLAIM_TEXT,
    }


def _compact_report(report: str, packet: dict[str, Any]) -> dict[str, Any]:
    policy = packet.get("policy_metadata", {})
    return {
        "title": "HackAIthon MVP Diagnostic Routing Report",
        "run_id": packet.get("run_id"),
        "line_count": len(report.splitlines()),
        "has_policy_section": isinstance(policy, dict) and bool(policy),
        "human_review_required": True,
        "non_claim": NON_CLAIM_TEXT,
    }


def _handler_static_evidence_loader(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    context: DAGExecutionContext = state["context"]
    static_inputs = context.static_inputs
    records = static_inputs.get("static_evidence_records")
    if records is None:
        records = load_static_evidence()
    records = [dict(record) for record in records]
    ticker_records = [record for record in records if str(record.get("ticker", "")).upper() == context.ticker]
    selected = None
    for record in ticker_records:
        if int(record.get("horizon", context.horizon_steps)) == context.horizon_steps:
            selected = dict(record)
            break
    if selected is None and ticker_records:
        selected = dict(ticker_records[0])
    warnings: list[str] = []
    if selected is None:
        warnings.append("no matching local sample evidence for DAG context")
    state.update(
        {
            "static_evidence_records": records,
            "ticker_evidence_records": ticker_records,
            "selected_evidence_record": selected,
        }
    )
    return _node_success(
        {
            "record_count": len(records),
            "ticker_record_count": len(ticker_records),
            "selected_record_id": selected.get("record_id") if isinstance(selected, dict) else None,
        },
        warnings,
    )


def _handler_engine_runtime(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    context: DAGExecutionContext = state["context"]
    selected = state.get("selected_evidence_record")
    records = state.get("ticker_evidence_records", [])
    spec = _matching_spec(selected, context.horizon_steps) if isinstance(selected, dict) else _fallback_spec(context)
    result = run_engine(spec, evidence_records=records)
    result_payload = result.to_dict() if isinstance(result, EngineResult) else dict(result)
    state.update({"engine_spec": spec.to_dict(), "engine_result": result_payload})
    return _node_success(_compact_result_payload(result_payload), list(result_payload.get("warnings", []) or []))


def _handler_forecast_diagnostic_engine(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    context: DAGExecutionContext = state["context"]
    engine_result = state.get("engine_result", {})
    selected = state.get("selected_evidence_record")
    diagnostic = run_forecast_diagnostic(
        engine_result,
        evidence_record=selected if isinstance(selected, dict) else None,
        adapter_metadata={"timeframe": context.timeframe},
    )
    if diagnostic.get("horizon") is not None:
        diagnostic["horizon_steps"] = int(diagnostic["horizon"])
    else:
        diagnostic["horizon_steps"] = context.horizon_steps
    diagnostic["ticker"] = context.ticker
    quant_output = _quant_core_from_forecast(context, diagnostic, engine_result)
    state.update({"forecast_diagnostic": diagnostic, "quant_core_output": quant_output})
    return _node_success(
        {
            "forecast_diagnostic": diagnostic.get("forecast_diagnostic"),
            "confidence": diagnostic.get("confidence"),
            "baseline_status": diagnostic.get("baseline_status"),
            "evidence_status": diagnostic.get("evidence_status"),
            "quant_signal": quant_output.get("quant_signal"),
        },
        list(diagnostic.get("warnings", []) or []),
    )


def _handler_quant_core_policy_runtime(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    diagnostic = dict(state.get("forecast_diagnostic", {}))
    quant_output = dict(state.get("quant_core_output", {}))
    if policy is None:
        quant_output["policy_runtime_status"] = "policy_not_applied"
        state["quant_core_output"] = quant_output
        state["policy_metadata"] = {"policy_runtime_status": "policy_not_applied"}
        return _node_success({"policy_runtime_status": "policy_not_applied"})
    runtime_output = apply_registered_policy_to_forecast(diagnostic, policy)
    quant_output["quant_signal"] = runtime_output.get("forecast_diagnostic", quant_output.get("quant_signal"))
    quant_output["forecast_diagnostic_counts"] = _forecast_counts(str(quant_output["quant_signal"]))
    for field in POLICY_FIELDS:
        if field in runtime_output:
            quant_output[field] = runtime_output[field]
    quant_output["forecast_diagnostic_sample"] = [
        {
            **(quant_output.get("forecast_diagnostic_sample", [{}])[0] if quant_output.get("forecast_diagnostic_sample") else {}),
            "forecast_diagnostic": runtime_output.get("forecast_diagnostic"),
        }
    ]
    state.update(
        {
            "forecast_diagnostic": runtime_output,
            "pre_policy_forecast_diagnostic": runtime_output.get("pre_policy_forecast_diagnostic"),
            "quant_core_output": quant_output,
            "policy_metadata": _policy_metadata(quant_output),
        }
    )
    return _node_success(_policy_metadata(quant_output))


def _handler_scenario_engine(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    output = run_scenario_engine(state["quant_core_output"])
    state["scenario_output"] = output
    return _node_success(
        {"scenario": output.get("scenario"), "scenario_confidence": output.get("scenario_confidence")}
    )


def _handler_risk_governance_engine(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    output = run_risk_governance(state["quant_core_output"], state["scenario_output"])
    state["risk_output"] = output
    return _node_success({"risk_level": output.get("risk_level"), "risk_flags": output.get("risk_flags", [])})


def _handler_decision_lane_engine(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    output = run_decision_lane(state["quant_core_output"], state["scenario_output"], state["risk_output"])
    state["decision_output"] = output
    return _node_success({"decision_lane": output.get("decision_lane"), "human_review_required": True})


def _handler_market_context_engine(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    context: DAGExecutionContext = state["context"]
    output = run_market_context(context.ticker)
    state["market_context_output"] = output
    return _node_success(
        {
            "market_context_status": output.get("market_context_status"),
            "live_context_enabled": output.get("live_context_enabled"),
        }
    )


def _handler_calibration_engine(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    output = run_calibration(
        state["quant_core_output"],
        state["scenario_output"],
        state["risk_output"],
        state["decision_output"],
    )
    state["calibration_output"] = output
    return _node_success(
        {
            "calibrated_confidence": output.get("calibrated_confidence"),
            "calibration_policy": output.get("calibration_policy"),
            "fine_tuning_performed": output.get("fine_tuning_performed"),
        }
    )


def _handler_research_allocation_view(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    output = run_portfolio_diagnostic_allocator(
        state["decision_output"],
        state["risk_output"],
        state["calibration_output"],
    )
    state["allocation_output"] = output
    return _node_success(
        {"allocation_view": output.get("allocation_view"), "allocation_is_advisory": output.get("allocation_is_advisory")}
    )


def _handler_phase_router(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    context: DAGExecutionContext = state["context"]
    output = run_phase_router(state["decision_output"], state["risk_output"], state["allocation_output"])
    state["router_output"] = output
    chain_output = {
        "ticker": context.ticker,
        "timeframe": context.timeframe,
        "layer_1_quant_core": state["quant_core_output"],
        "layer_2_scenario": state["scenario_output"],
        "layer_3_risk_governance": state["risk_output"],
        "layer_4_decision_lane": state["decision_output"],
        "layer_5_market_context": state["market_context_output"],
        "layer_6_calibration": state["calibration_output"],
        "layer_7_portfolio_diagnostic_allocator": state["allocation_output"],
        "layer_8_phase_router": output,
        "non_claim": NON_CLAIM_TEXT,
    }
    state["chain_output"] = chain_output
    return _node_success({"route": output.get("route"), "dashboard_status": output.get("dashboard_status")})


def _handler_evidence_packet(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    context: DAGExecutionContext = state["context"]
    packet = build_evidence_packet(
        state["chain_output"],
        run_metadata={"run_id": context.run_id, "generated_at": "2026-06-20T00:00:00+00:00"},
    )
    state["evidence_packet"] = packet
    return _node_success(_compact_packet(packet))


def _handler_diagnostic_report(state: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    packet = state["evidence_packet"]
    report = render_diagnostic_report(packet)
    state["diagnostic_report_text"] = report
    state["diagnostic_report"] = _compact_report(report, packet)
    return _node_success(state["diagnostic_report"])


HANDLERS: dict[str, Handler] = {
    "static_evidence_loader": _handler_static_evidence_loader,
    "engine_runtime": _handler_engine_runtime,
    "forecast_diagnostic_engine": _handler_forecast_diagnostic_engine,
    "quant_core_policy_runtime": _handler_quant_core_policy_runtime,
    "scenario_engine": _handler_scenario_engine,
    "risk_governance_engine": _handler_risk_governance_engine,
    "decision_lane_engine": _handler_decision_lane_engine,
    "market_context_engine": _handler_market_context_engine,
    "calibration_engine": _handler_calibration_engine,
    "research_allocation_view": _handler_research_allocation_view,
    "phase_router": _handler_phase_router,
    "evidence_packet": _handler_evidence_packet,
    "diagnostic_report": _handler_diagnostic_report,
}


def _context_from_dict(payload: dict[str, Any]) -> DAGExecutionContext:
    return DAGExecutionContext.from_dict(payload)


def _nodes_by_id(nodes: tuple[dict, ...]) -> dict[str, dict]:
    return {str(node["node_id"]): node for node in nodes}


def _missing_required_inputs(node: dict[str, Any], state: dict[str, Any]) -> list[str]:
    return [field for field in node.get("required_inputs", []) if field not in state]


def _result_for_failure(node_id: str, message: str, warnings: list[str] | None = None) -> dict[str, Any]:
    return DAGNodeResult(
        node_id=node_id,
        status="failed",
        outputs={},
        warnings=tuple(warnings or []),
        error=message,
        claim_boundary=claim_boundary(),
        non_claim=NON_CLAIM_TEXT,
    ).to_dict()


def _sanitize_final_state(state: dict[str, Any]) -> dict[str, Any]:
    packet = state.get("evidence_packet", {})
    policy = state.get("policy_metadata", {})
    final = {
        "run_id": state["context"].run_id,
        "ticker": state["context"].ticker,
        "timeframe": state["context"].timeframe,
        "horizon_steps": state["context"].horizon_steps,
        "engine_result": _compact_result_payload(state.get("engine_result", {})),
        "forecast_diagnostic": _compact_forecast_payload(state.get("forecast_diagnostic", {})),
        "quant_core_output": {
            "quant_signal": state.get("quant_core_output", {}).get("quant_signal"),
            "consensus_strength": state.get("quant_core_output", {}).get("consensus_strength"),
            "engine_count_checked": state.get("quant_core_output", {}).get("engine_count_checked"),
            "completed_count": state.get("quant_core_output", {}).get("completed_count"),
            "skipped_missing_evidence_count": state.get("quant_core_output", {}).get("skipped_missing_evidence_count"),
            "policy_runtime_status": state.get("quant_core_output", {}).get("policy_runtime_status"),
        },
        "policy_metadata": policy,
        "chain_output": _compact_chain_output(state) if "chain_output" in state else {},
        "evidence_packet": _compact_packet(packet) if isinstance(packet, dict) and packet else {},
        "diagnostic_report": state.get("diagnostic_report", {}),
        "claim_boundary": claim_boundary(),
        "non_claim": NON_CLAIM_TEXT,
    }
    if "storage_context_metadata" in state:
        final.update(state["storage_context_metadata"])
    assert_no_forbidden_public_terms(final)
    return final


def execute_diagnostic_dag(
    nodes: tuple[dict, ...],
    context: dict,
    *,
    policy: dict | None = None,
    storage_context: dict | None = None,
) -> dict:
    """Execute the diagnostic DAG with static/local handlers only."""

    validation = validate_dag(nodes)
    if not validation["is_valid"]:
        minimal_context = _context_from_dict(context)
        return DAGExecutionResult(
            run_id=minimal_context.run_id or "",
            ticker=minimal_context.ticker,
            timeframe=minimal_context.timeframe,
            horizon_steps=minimal_context.horizon_steps,
            dag_valid=False,
            execution_status="failed",
            topological_order=tuple(validation["topological_order"]),
            node_results=[],
            final_state={"validation_errors": validation["errors"], "claim_boundary": claim_boundary()},
            audit_trail=[],
            claim_boundary=claim_boundary(),
            non_claim=NON_CLAIM_TEXT,
        ).to_dict()

    execution_context = _context_from_dict(context)
    node_lookup = _nodes_by_id(nodes)
    order = topological_sort(nodes)
    state: dict[str, Any] = {
        "context": execution_context,
        "ticker": execution_context.ticker,
        "timeframe": execution_context.timeframe,
        "horizon_steps": execution_context.horizon_steps,
        "run_id": execution_context.run_id,
        "static_inputs": execution_context.static_inputs,
        "metadata": execution_context.metadata,
    }
    if policy is not None:
        state["policy"] = policy
    if storage_context is not None:
        storage_status = str(storage_context.get("storage_context_status", "missing"))
        market_bar_count = int(storage_context.get("market_bar_count", 0) or 0)
        state["storage_context"] = dict(storage_context)
        state["storage_context_metadata"] = {
            "storage_context_status": storage_status,
            "market_bar_count": market_bar_count,
            "local_storage_available": storage_status == "provided" and market_bar_count > 0,
        }

    node_results: list[dict[str, Any]] = []
    audit_trail: list[dict[str, Any]] = []
    warnings: list[str] = []
    failed = False
    for node_id in order:
        node = node_lookup[node_id]
        started_at = _utc_now()
        required = bool(node.get("is_required", True))
        missing = _missing_required_inputs(node, state)
        if missing:
            message = f"missing required inputs: {', '.join(missing)}"
            result = _result_for_failure(node_id, message)
            node_results.append(result)
            audit_trail.append(
                {
                    "node_id": node_id,
                    "status": "failed",
                    "started_at": started_at,
                    "completed_at": _utc_now(),
                    "required": required,
                    "warning_count": 0,
                    "error": message,
                }
            )
            if required:
                failed = True
                break
            warnings.append(f"{node_id}: {message}")
            continue
        handler = HANDLERS.get(node_id)
        if handler is None:
            message = f"no handler registered for {node_id}"
            result = _result_for_failure(node_id, message)
            node_results.append(result)
            audit_trail.append(
                {
                    "node_id": node_id,
                    "status": "failed",
                    "started_at": started_at,
                    "completed_at": _utc_now(),
                    "required": required,
                    "warning_count": 0,
                    "error": message,
                }
            )
            if required:
                failed = True
                break
            warnings.append(f"{node_id}: {message}")
            continue
        try:
            handler_result = handler(state, policy)
            result = DAGNodeResult(
                node_id=node_id,
                status="completed",
                outputs=handler_result.get("outputs", {}),
                warnings=tuple(handler_result.get("warnings", []) or []),
                claim_boundary=claim_boundary(),
                non_claim=NON_CLAIM_TEXT,
            ).to_dict()
        except Exception as exc:
            message = str(exc)
            result = _result_for_failure(node_id, message)
            if required:
                failed = True
            else:
                warnings.append(f"{node_id}: {message}")
        node_results.append(result)
        if result["warnings"]:
            warnings.extend(f"{node_id}: {warning}" for warning in result["warnings"])
        audit_trail.append(
            {
                "node_id": node_id,
                "status": result["status"],
                "started_at": started_at,
                "completed_at": _utc_now(),
                "required": required,
                "warning_count": len(result["warnings"]),
                "error": result.get("error"),
            }
        )
        if failed:
            break

    status = "failed" if failed else ("completed_with_warnings" if warnings else "completed")
    final_state = _sanitize_final_state(state) if not failed else {
        "run_id": execution_context.run_id,
        "ticker": execution_context.ticker,
        "timeframe": execution_context.timeframe,
        "horizon_steps": execution_context.horizon_steps,
        "warnings": warnings,
        "claim_boundary": claim_boundary(),
        "non_claim": NON_CLAIM_TEXT,
    }
    if failed and "storage_context_metadata" in state:
        final_state.update(state["storage_context_metadata"])
    result = DAGExecutionResult(
        run_id=execution_context.run_id or "",
        ticker=execution_context.ticker,
        timeframe=execution_context.timeframe,
        horizon_steps=execution_context.horizon_steps,
        dag_valid=True,
        execution_status=status,
        topological_order=order,
        node_results=node_results,
        final_state=final_state,
        audit_trail=audit_trail,
        claim_boundary=claim_boundary(),
        non_claim=NON_CLAIM_TEXT,
    ).to_dict()
    assert_no_forbidden_public_terms(result)
    return result
