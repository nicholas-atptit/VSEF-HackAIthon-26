"""Optional local storage bridge for diagnostic DAG executions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.hackaithon_mvp.local_storage.availability_index import build_availability_index
from src.hackaithon_mvp.local_storage import parquet_adapter
from src.hackaithon_mvp.local_storage.storage_paths import build_partition_path
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe

from .dag_registry import build_default_diagnostic_dag
from .dag_schema import NON_CLAIM_TEXT, claim_boundary


BRIDGE_NON_CLAIM_TEXT = "Optional local storage bridge only; diagnostic research boundary applies."
BRIDGE_CLAIM_BOUNDARY = {
    **claim_boundary(),
    "local_files_only": True,
    "server_database_created": False,
    "data_gateway_created": False,
    "storage_write_default": False,
}
POLICY_FIELDS = (
    "policy_id",
    "policy_name",
    "policy_runtime_status",
    "pre_policy_forecast_diagnostic",
    "policy_validation_accuracy",
    "policy_validation_balanced_accuracy",
    "policy_validation_coverage",
)


def _final_state(execution_result: dict[str, Any]) -> dict[str, Any]:
    state = execution_result.get("final_state", {})
    return state if isinstance(state, dict) else {}


def _policy_metadata(execution_result: dict[str, Any]) -> dict[str, Any]:
    final_state = _final_state(execution_result)
    policy = final_state.get("policy_metadata", {})
    if not isinstance(policy, dict):
        policy = {}
    quant = final_state.get("quant_core_output", {})
    if isinstance(quant, dict):
        policy = {**{field: quant[field] for field in POLICY_FIELDS if field in quant}, **policy}
    return {field: policy[field] for field in POLICY_FIELDS if field in policy}


def _warning_count(execution_result: dict[str, Any]) -> int:
    total = 0
    for node_result in execution_result.get("node_results", []) or []:
        if isinstance(node_result, dict):
            total += len(node_result.get("warnings", []) or [])
    return total


def _route(execution_result: dict[str, Any]) -> str | None:
    final_state = _final_state(execution_result)
    chain = final_state.get("chain_output", {})
    if isinstance(chain, dict):
        router = chain.get("layer_8_phase_router", {})
        if isinstance(router, dict) and router.get("route") is not None:
            return str(router.get("route"))
    packet = final_state.get("evidence_packet", {})
    if isinstance(packet, dict):
        routing = packet.get("routing_summary", {})
        if isinstance(routing, dict) and routing.get("route") is not None:
            return str(routing.get("route"))
    return None


def _created_at(execution_result: dict[str, Any]) -> str:
    audit = execution_result.get("audit_trail", []) or []
    if audit and isinstance(audit[-1], dict) and audit[-1].get("completed_at"):
        return str(audit[-1]["completed_at"])
    return "1970-01-01T00:00:00+00:00"


def _storage_metadata(execution_result: dict[str, Any]) -> dict[str, Any]:
    final_state = _final_state(execution_result)
    metadata: dict[str, Any] = {}
    for field in ("storage_context_status", "market_bar_count", "local_storage_available"):
        if field in final_state:
            metadata[field] = final_state[field]
    return metadata


def build_dag_run_record(execution_result: dict) -> dict:
    """Build a compact run-level storage record from a DAG execution result."""

    policy = _policy_metadata(execution_result)
    record = {
        "run_id": execution_result.get("run_id"),
        "ticker": execution_result.get("ticker"),
        "timeframe": execution_result.get("timeframe"),
        "horizon_steps": execution_result.get("horizon_steps"),
        "execution_status": execution_result.get("execution_status"),
        "node_count": len(execution_result.get("node_results", []) or []),
        "warning_count": _warning_count(execution_result),
        "policy_id": policy.get("policy_id"),
        "policy_name": policy.get("policy_name"),
        "policy_runtime_status": policy.get("policy_runtime_status"),
        "route": _route(execution_result),
        "created_at": _created_at(execution_result),
        "claim_boundary": dict(BRIDGE_CLAIM_BOUNDARY),
        "non_claim": BRIDGE_NON_CLAIM_TEXT,
    }
    record.update(_storage_metadata(execution_result))
    return record


def build_dag_node_records(execution_result: dict) -> tuple[dict, ...]:
    """Build compact per-node records without storing raw node outputs."""

    specs = {node["node_id"]: node for node in build_default_diagnostic_dag()}
    run_id = execution_result.get("run_id")
    records: list[dict[str, Any]] = []
    for node_result in execution_result.get("node_results", []) or []:
        if not isinstance(node_result, dict):
            continue
        node_id = str(node_result.get("node_id", ""))
        spec = specs.get(node_id, {})
        records.append(
            {
                "run_id": run_id,
                "node_id": node_id,
                "node_name": spec.get("node_name", node_id),
                "layer": spec.get("layer", "unknown"),
                "status": node_result.get("status"),
                "warning_count": len(node_result.get("warnings", []) or []),
                "produces": list(spec.get("produces", []) or []),
                "claim_boundary": dict(BRIDGE_CLAIM_BOUNDARY),
            }
        )
    return tuple(records)


def _artifact_base(execution_result: dict[str, Any], artifact_kind: str) -> dict[str, Any]:
    policy = _policy_metadata(execution_result)
    base = {
        "run_id": execution_result.get("run_id"),
        "ticker": execution_result.get("ticker"),
        "timeframe": execution_result.get("timeframe"),
        "horizon_steps": execution_result.get("horizon_steps"),
        "artifact_kind": artifact_kind,
        "execution_status": execution_result.get("execution_status"),
        "route": _route(execution_result),
        "created_at": _created_at(execution_result),
        "claim_boundary": dict(BRIDGE_CLAIM_BOUNDARY),
        "non_claim": BRIDGE_NON_CLAIM_TEXT,
    }
    base.update(policy)
    base.update(_storage_metadata(execution_result))
    return base


def _evidence_packet_record(execution_result: dict[str, Any]) -> dict[str, Any] | None:
    packet = _final_state(execution_result).get("evidence_packet", {})
    if not isinstance(packet, dict) or not packet:
        return None
    return {
        **_artifact_base(execution_result, "evidence_packet"),
        "run_mode": packet.get("run_mode"),
        "engine_universe_summary": packet.get("engine_universe_summary", {}),
        "forecast_diagnostic_summary": packet.get("forecast_diagnostic_summary", {}),
        "chain_summary": packet.get("chain_summary", {}),
        "risk_summary": packet.get("risk_summary", {}),
        "routing_summary": packet.get("routing_summary", {}),
        "human_review_required": True,
    }


def _diagnostic_report_record(execution_result: dict[str, Any]) -> dict[str, Any] | None:
    report = _final_state(execution_result).get("diagnostic_report", {})
    if not isinstance(report, dict) or not report:
        return None
    return {
        **_artifact_base(execution_result, "diagnostic_report"),
        "title": report.get("title"),
        "line_count": report.get("line_count"),
        "has_policy_section": report.get("has_policy_section"),
        "human_review_required": True,
    }


def build_dag_artifact_records(execution_result: dict) -> dict:
    """Build compact storage records for run, packet, and report artifacts."""

    evidence_record = _evidence_packet_record(execution_result)
    report_record = _diagnostic_report_record(execution_result)
    return {
        "dag_runs": (build_dag_run_record(execution_result),),
        "evidence_packets": (evidence_record,) if evidence_record is not None else (),
        "diagnostic_reports": (report_record,) if report_record is not None else (),
    }


def _combined_storage_format(write_results: dict[str, dict[str, Any]]) -> str | None:
    formats = {
        str(result.get("storage_format"))
        for result in write_results.values()
        if isinstance(result, dict) and result.get("storage_format")
    }
    if not formats:
        return None
    if len(formats) == 1:
        return next(iter(formats))
    return "mixed"


def persist_dag_execution(
    execution_result: dict,
    *,
    storage_root: str,
) -> dict:
    """Persist compact DAG records under an explicit local storage root."""

    root = str(storage_root).strip()
    if not root:
        raise ValueError("storage_root must be non-empty")
    run_id = str(execution_result.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("execution_result.run_id must be non-empty")

    artifacts = build_dag_artifact_records(execution_result)
    write_results: dict[str, dict[str, Any]] = {}
    records_written = 0
    for dataset_kind, records in artifacts.items():
        if not records:
            continue
        result = parquet_adapter.write_dataset_records(root, dataset_kind, records, run_id=run_id)
        write_results[dataset_kind] = result
        records_written += int(result.get("row_count", 0))

    return {
        "storage_write_enabled": True,
        "storage_root": root.replace("\\", "/"),
        "records_written": records_written,
        "write_results": write_results,
        "storage_format": _combined_storage_format(write_results),
        "claim_boundary": dict(BRIDGE_CLAIM_BOUNDARY),
        "non_claim": BRIDGE_NON_CLAIM_TEXT,
    }


def _read_market_bars_for_date(root: str, ticker: str, timeframe: str, date: str | None) -> tuple[dict, ...]:
    if date is not None:
        return parquet_adapter.read_dataset_records(
            root,
            "market_bars",
            ticker=ticker,
            timeframe=timeframe,
            date=date,
        )

    base = Path(build_partition_path(root, "market_bars", ticker=ticker, timeframe=timeframe))
    records: list[dict[str, Any]] = []
    if not base.exists():
        return ()
    for partition in sorted(base.glob("date=*")):
        if not partition.is_dir():
            continue
        records.extend(parquet_adapter.read_records(str(partition / "part.parquet")))
    return tuple(records)


def load_static_context_from_storage(
    *,
    storage_root: str,
    ticker: str,
    timeframe: str,
    date: str | None = None,
) -> dict:
    """Load optional local market-bar context from the local storage adapter."""

    root = str(storage_root).strip()
    if not root:
        raise ValueError("storage_root must be non-empty")
    normalized_ticker = str(ticker).strip().upper()
    normalized_timeframe = normalize_timeframe(timeframe)
    records = _read_market_bars_for_date(root, normalized_ticker, normalized_timeframe, date)
    if not records:
        return {
            "storage_context_status": "missing",
            "ticker": normalized_ticker,
            "timeframe": normalized_timeframe,
            "market_bar_count": 0,
            "availability_index": build_availability_index(()),
            "claim_boundary": dict(BRIDGE_CLAIM_BOUNDARY),
            "non_claim": BRIDGE_NON_CLAIM_TEXT,
        }

    availability = build_availability_index(records)
    return {
        "storage_context_status": "provided",
        "ticker": normalized_ticker,
        "timeframe": normalized_timeframe,
        "market_bar_count": len(records),
        "availability_index": availability,
        "claim_boundary": dict(BRIDGE_CLAIM_BOUNDARY),
        "non_claim": BRIDGE_NON_CLAIM_TEXT,
    }
