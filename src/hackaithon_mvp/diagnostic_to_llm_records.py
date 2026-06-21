"""Build compact LLM-readable records from local diagnostic outputs."""

from __future__ import annotations

from typing import Any

from src.hackaithon_mvp.llm_storage_contract import (
    CLAIM_BOUNDARY,
    CREATED_AT,
    NON_CLAIM_TEXT,
    validate_llm_readable_record,
)


def _request_context(result: dict[str, Any]) -> dict[str, str]:
    validation = result.get("input_validation", {}) if isinstance(result, dict) else {}
    payload = validation.get("normalized_payload", {}) if isinstance(validation, dict) else {}
    request = payload.get("request", {}) if isinstance(payload, dict) else {}
    return {
        "ticker": str(request.get("ticker", "")),
        "timeframe": str(request.get("timeframe", "")),
        "run_id": str(request.get("run_id", "")),
    }


def _base_record(
    *,
    record_id: str,
    record_type: str,
    title: str,
    summary: str,
    content: dict[str, Any],
    source_module: str,
    context: dict[str, str] | None = None,
    claim_boundary: dict[str, Any] | None = None,
    non_claim: str | None = None,
) -> dict[str, Any]:
    record = {
        "record_id": record_id,
        "record_type": record_type,
        "title": title,
        "summary": summary,
        "content": content,
        "source_module": source_module,
        "created_at": CREATED_AT,
        "claim_boundary": dict(claim_boundary or CLAIM_BOUNDARY),
        "non_claim": non_claim or NON_CLAIM_TEXT,
        "human_review_required": True,
        "read_only": True,
    }
    for field in ("ticker", "timeframe", "run_id"):
        value = (context or {}).get(field)
        if value:
            record[field] = value
    return record


def _finalize(records: list[dict[str, Any]]) -> tuple[dict, ...]:
    normalized_records: list[dict[str, Any]] = []
    for record in records:
        validation = validate_llm_readable_record(record)
        if not validation["is_valid"]:
            raise ValueError(f"invalid LLM-readable record {record.get('record_id')}: {validation['errors']}")
        normalized_records.append(validation["normalized_record"])
    return tuple(normalized_records)


def build_llm_records_from_diagnostic_result(result: dict) -> tuple[dict, ...]:
    """Convert a canonical diagnostic engine result into compact read-only records."""

    context = _request_context(result)
    prefix = context.get("run_id") or "diagnostic-engine-run"
    engine_status = result.get("engine_status")
    completeness = result.get("engine_completeness", {})
    ml_summary = result.get("ml_engine", {})
    risk_summary = result.get("risk_engine_v2", {})
    scenario_summary = result.get("scenario_engine_v2", {})
    decision = result.get("decision_lane_v2", {})
    dag_output = result.get("dag_output", {})
    evidence = result.get("evidence", {})
    dashboard = result.get("dashboard_artifact", {})
    records = [
        _base_record(
            record_id=f"{prefix}:engine_run_summary",
            record_type="engine_run_summary",
            title="Diagnostic engine run summary",
            summary="Canonical local diagnostic engine run summary.",
            content={
                "engine_status": engine_status,
                "completeness_status": completeness.get("completeness_status"),
                "human_review_required": True,
                "auto_execution_allowed": False,
            },
            source_module="diagnostic_engine",
            context=context,
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:diagnostic_report",
            record_type="diagnostic_report",
            title="Diagnostic output summary",
            summary="Compact diagnostic output view for reviewer context.",
            content={
                "dag_execution_status": dag_output.get("execution_status"),
                "dashboard_readiness_status": dashboard.get("readiness_status"),
                "decision_lane": decision.get("lane"),
            },
            source_module="diagnostic_engine",
            context=context,
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:ml_diagnostic_summary",
            record_type="ml_diagnostic_summary",
            title="ML diagnostic summary",
            summary="Baseline ML-only diagnostic summary over provided records.",
            content={
                "ml_engine_status": ml_summary.get("ml_engine_status"),
                "model_count": ml_summary.get("model_count"),
                "family_count": ml_summary.get("family_count"),
                "agreement_status": ml_summary.get("agreement_status"),
                "signal_quality": (ml_summary.get("signal_quality") or {}).get("quality_status"),
                "recommended_review_lane": ml_summary.get("recommended_review_lane"),
            },
            source_module="ml_diagnostic_engine",
            context=context,
            claim_boundary=ml_summary.get("claim_boundary") or result.get("claim_boundary"),
            non_claim=ml_summary.get("non_claim") or result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:risk_assessment",
            record_type="risk_assessment",
            title="Risk Engine V2 assessment",
            summary="Compact diagnostic risk assessment.",
            content={
                "risk_engine_status": risk_summary.get("risk_engine_status"),
                "risk_level": risk_summary.get("risk_level"),
                "risk_score": risk_summary.get("risk_score"),
                "blocking_flags": list(risk_summary.get("blocking_flags", []) or []),
                "risk_review_reason": risk_summary.get("risk_review_reason"),
            },
            source_module="risk_engine_v2",
            context=context,
            claim_boundary=risk_summary.get("claim_boundary") or result.get("claim_boundary"),
            non_claim=risk_summary.get("non_claim") or result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:scenario_assessment",
            record_type="scenario_assessment",
            title="Scenario Engine V2 assessment",
            summary="Local diagnostic stress-context summary.",
            content={
                "scenario_engine_status": scenario_summary.get("scenario_engine_status"),
                "scenario_count": scenario_summary.get("scenario_count"),
                "dominant_scenario": scenario_summary.get("dominant_scenario"),
                "scenario_risk_level": scenario_summary.get("scenario_risk_level"),
                "stability_status": scenario_summary.get("stability_status"),
            },
            source_module="scenario_engine_v2",
            context=context,
            claim_boundary=scenario_summary.get("claim_boundary") or result.get("claim_boundary"),
            non_claim=scenario_summary.get("non_claim") or result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:decision_lane_output",
            record_type="decision_lane_output",
            title="Decision Lane V2 output",
            summary="Human-review diagnostic routing output.",
            content={
                "decision_lane_status": decision.get("decision_lane_status"),
                "lane": decision.get("lane"),
                "review_priority": decision.get("review_priority"),
                "required_reviews": list(decision.get("required_reviews", []) or []),
                "blocking_reasons": list(decision.get("blocking_reasons", []) or []),
                "human_review_required": True,
                "auto_execution_allowed": False,
            },
            source_module="decision_lane_v2",
            context=context,
            claim_boundary=decision.get("claim_boundary") or result.get("claim_boundary"),
            non_claim=decision.get("non_claim") or result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:evidence_packet",
            record_type="evidence_packet",
            title="Evidence packet summary",
            summary="Compact evidence packet summary without raw row dumps.",
            content={
                "evidence_sections": sorted(str(key) for key in evidence.keys()),
                "has_v2_evidence_packet": bool(evidence.get("v2_evidence_packet")),
                "has_dag_evidence_packet": bool(evidence.get("dag_evidence_packet")),
                "human_review_required": True,
            },
            source_module="diagnostic_engine",
            context=context,
            claim_boundary=evidence.get("claim_boundary") or result.get("claim_boundary"),
            non_claim=evidence.get("non_claim") or result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:claim_boundary",
            record_type="claim_boundary",
            title="Diagnostic engine claim boundary",
            summary="Boundary flags for retrieved diagnostic evidence.",
            content=dict(result.get("claim_boundary", CLAIM_BOUNDARY)),
            source_module="diagnostic_engine",
            context=context,
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{prefix}:limitation_note",
            record_type="limitation_note",
            title="Diagnostic engine limitation note",
            summary="Limits for using this local diagnostic evidence.",
            content={
                "provided_records_only": True,
                "human_review_required": True,
                "auto_execution_allowed": False,
                "no_live_data": True,
                "no_provider_calls": True,
                "no_training": True,
                "no_inference": True,
                "no_benchmark_rerun": True,
            },
            source_module="diagnostic_engine",
            context=context,
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
    ]
    return _finalize(records)


def build_llm_records_from_hardening_gate(result: dict) -> tuple[dict, ...]:
    """Convert a hardening gate result into compact read-only records."""

    status = str(result.get("hardening_status") or "hardening_gate")
    records = [
        _base_record(
            record_id=f"{status}:hardening_gate_report",
            record_type="hardening_gate_report",
            title="Diagnostic engine hardening gate report",
            summary="Local hardening gate status and check counts.",
            content={
                "hardening_status": result.get("hardening_status"),
                "check_count": result.get("check_count"),
                "passed_count": result.get("passed_count"),
                "failed_checks": [
                    check.get("check_id")
                    for check in result.get("checks", [])
                    if isinstance(check, dict) and check.get("passed") is not True
                ],
            },
            source_module="diagnostic_engine_hardening_gate",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{status}:claim_boundary",
            record_type="claim_boundary",
            title="Hardening gate claim boundary",
            summary="Boundary flags for the local hardening gate.",
            content=dict(result.get("claim_boundary", CLAIM_BOUNDARY)),
            source_module="diagnostic_engine_hardening_gate",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{status}:limitation_note",
            record_type="limitation_note",
            title="Hardening gate limitation note",
            summary="Limits for interpreting the local hardening gate.",
            content={
                "local_gate_only": True,
                "writes_files": False,
                "human_review_required": True,
                "auto_execution_allowed": False,
            },
            source_module="diagnostic_engine_hardening_gate",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
    ]
    return _finalize(records)


def build_llm_records_from_diagram_readiness(result: dict) -> tuple[dict, ...]:
    """Convert diagram readiness output into compact read-only records."""

    status = str(result.get("readiness_status") or "diagram_readiness")
    coverage = result.get("diagram_coverage_matrix_summary", {})
    records = [
        _base_record(
            record_id=f"{status}:architecture_alignment",
            record_type="architecture_alignment",
            title="Architecture alignment summary",
            summary="Local architecture alignment status for diagnostic evidence.",
            content={
                "readiness_status": result.get("readiness_status"),
                "architecture_alignment_status": result.get("architecture_alignment_status"),
                "checks": dict(result.get("checks", {}) or {}),
                "future_scope_count": len(result.get("remaining_future_scope", []) or []),
            },
            source_module="diagram_demo_readiness",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{status}:diagram_coverage",
            record_type="diagram_coverage",
            title="Diagram coverage summary",
            summary="Diagram-to-code coverage summary for local demo readiness.",
            content={
                "coverage_status": coverage.get("coverage_status"),
                "block_count": coverage.get("block_count"),
                "required_block_count": coverage.get("required_block_count"),
                "status_counts": dict(coverage.get("status_counts", {}) or {}),
                "diagnostic_engine_core_ready": {
                    "gateway_input_contract_ready": result.get("gateway_input_contract_ready"),
                    "ml_diagnostic_engine_ready": result.get("ml_diagnostic_engine_ready"),
                    "risk_engine_v2_ready": result.get("risk_engine_v2_ready"),
                    "scenario_engine_v2_ready": result.get("scenario_engine_v2_ready"),
                    "decision_lane_v2_ready": result.get("decision_lane_v2_ready"),
                    "hardening_gate_status": result.get("hardening_gate_status"),
                },
            },
            source_module="diagram_demo_readiness",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{status}:claim_boundary",
            record_type="claim_boundary",
            title="Diagram readiness claim boundary",
            summary="Boundary flags for diagram readiness evidence.",
            content=dict(result.get("claim_boundary", CLAIM_BOUNDARY)),
            source_module="diagram_demo_readiness",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
        _base_record(
            record_id=f"{status}:limitation_note",
            record_type="limitation_note",
            title="Diagram readiness limitation note",
            summary="Limits for interpreting diagram readiness evidence.",
            content={
                "local_static_demo_only": True,
                "writes_files": False,
                "human_review_required": True,
                "no_live_data": True,
                "no_provider_calls": True,
                "no_training": True,
                "no_inference": True,
                "no_benchmark_rerun": True,
            },
            source_module="diagram_demo_readiness",
            claim_boundary=result.get("claim_boundary"),
            non_claim=result.get("non_claim"),
        ),
    ]
    return _finalize(records)
