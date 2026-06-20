"""Evidence packet builder for the HackAIthon MVP diagnostic chain."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe, timeframe_unit


PACKET_VERSION = "1.0"
RUN_MODE = "static_local_review"
SCOPE_TEXT = "Baseline ML-only diagnostic MVP for a banking stock-evaluation use case."
NON_CLAIM_TEXT = "Research diagnostic only; human review required."
CLAIM_BOUNDARY = (
    "no live data",
    "no provider API calls",
    "no model training",
    "no model inference",
    "no benchmark rerun",
    "no action guidance",
    "no financial advice",
)
LAYER_NAMES = {
    "layer_1_quant_core": "Quant Core",
    "layer_2_scenario": "Scenario",
    "layer_3_risk_governance": "Risk Governance",
    "layer_4_decision_lane": "Decision Lane",
    "layer_5_market_context": "Market Context",
    "layer_6_calibration": "Calibration",
    "review_cycle": "Review Cycle",
    "layer_7_portfolio_diagnostic_allocator": "Research Allocation View",
    "layer_8_phase_router": "Phase Router",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata_value(run_metadata: dict[str, Any] | None, key: str, default: Any) -> Any:
    if not isinstance(run_metadata, dict):
        return default
    return run_metadata.get(key, default)


def _list_warnings(chain_output: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for source in (
        chain_output.get("warnings"),
        chain_output.get("layer_1_quant_core", {}).get("warnings"),
    ):
        if isinstance(source, list):
            warnings.extend(str(item) for item in source)
    for boundary in CLAIM_BOUNDARY:
        if boundary not in warnings:
            warnings.append(boundary)
    return list(dict.fromkeys(warnings))


def _engine_universe_summary(quant_output: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine_count_checked": int(quant_output.get("engine_count_checked", 0)),
        "completed_count": int(quant_output.get("completed_count", 0)),
        "skipped_missing_evidence_count": int(quant_output.get("skipped_missing_evidence_count", 0)),
        "full_engine_catalog_included": False,
    }


def _forecast_diagnostic_summary(quant_output: dict[str, Any]) -> dict[str, Any]:
    counts = quant_output.get("forecast_diagnostic_counts", {})
    return {
        "enabled": bool(quant_output.get("forecast_diagnostic_engine_enabled", False)),
        "counts": dict(counts) if isinstance(counts, dict) else {},
        "sample_size": len(quant_output.get("forecast_diagnostic_sample", []) or []),
    }


def _chain_summary(chain_output: dict[str, Any]) -> dict[str, Any]:
    quant_output = chain_output.get("layer_1_quant_core", {})
    scenario_output = chain_output.get("layer_2_scenario", {})
    decision_output = chain_output.get("layer_4_decision_lane", {})
    calibration_output = chain_output.get("layer_6_calibration", {})
    return {
        "quant_signal": quant_output.get("quant_signal"),
        "consensus_strength": quant_output.get("consensus_strength"),
        "scenario": scenario_output.get("scenario"),
        "scenario_confidence": scenario_output.get("scenario_confidence"),
        "decision_lane": decision_output.get("decision_lane"),
        "calibrated_confidence": calibration_output.get("calibrated_confidence"),
    }


def _risk_summary(chain_output: dict[str, Any]) -> dict[str, Any]:
    risk_output = chain_output.get("layer_3_risk_governance", {})
    return {
        "risk_level": risk_output.get("risk_level"),
        "risk_flags": list(risk_output.get("risk_flags", []) or []),
        "risk_action": risk_output.get("risk_action"),
    }


def _routing_summary(chain_output: dict[str, Any]) -> dict[str, Any]:
    router_output = chain_output.get("layer_8_phase_router", {})
    decision_output = chain_output.get("layer_4_decision_lane", {})
    return {
        "route": router_output.get("route"),
        "dashboard_status": router_output.get("dashboard_status"),
        "decision_lane": decision_output.get("decision_lane"),
        "human_review_required": True,
    }


def _lineage_item(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {"layer": name}
    for key in (
        "quant_signal",
        "scenario",
        "risk_level",
        "decision_lane",
        "market_context_status",
        "calibration_policy",
        "cycle_mode",
        "allocation_view",
        "route",
    ):
        if key in payload:
            item[key] = payload[key]
    return item


def _lineage(chain_output: dict[str, Any]) -> list[dict[str, Any]]:
    lineage: list[dict[str, Any]] = []
    for key, name in LAYER_NAMES.items():
        payload = chain_output.get(key)
        if isinstance(payload, dict):
            lineage.append(_lineage_item(name, payload))
    return lineage


def build_evidence_packet(chain_output: dict, run_metadata: dict | None = None) -> dict:
    """Build a compact reviewer-facing packet from a final diagnostic chain output."""

    if not isinstance(chain_output, dict):
        raise ValueError("chain_output must be a dictionary")

    quant_output = chain_output.get("layer_1_quant_core", {})
    timeframe_value = chain_output.get("timeframe") or quant_output.get("timeframe") or "1d"
    canonical_timeframe = normalize_timeframe(str(timeframe_value))
    run_id = str(_metadata_value(run_metadata, "run_id", f"packet-{uuid.uuid4().hex}"))
    generated_at = str(_metadata_value(run_metadata, "generated_at", _utc_now()))

    packet = {
        "packet_version": PACKET_VERSION,
        "run_id": run_id,
        "ticker": str(chain_output.get("ticker", "")).upper(),
        "timeframe": canonical_timeframe,
        "timeframe_unit": timeframe_unit(canonical_timeframe),
        "run_mode": RUN_MODE,
        "scope": SCOPE_TEXT,
        "generated_at": generated_at,
        "engine_universe_summary": _engine_universe_summary(quant_output),
        "forecast_diagnostic_summary": _forecast_diagnostic_summary(quant_output),
        "chain_summary": _chain_summary(chain_output),
        "risk_summary": _risk_summary(chain_output),
        "routing_summary": _routing_summary(chain_output),
        "human_review_required": True,
        "claim_boundary": list(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "warnings": _list_warnings(chain_output),
        "lineage": _lineage(chain_output),
    }
    if isinstance(run_metadata, dict) and "data_readiness" in run_metadata:
        packet["data_readiness"] = run_metadata["data_readiness"]
    return packet


def _write_json(path: str, payload: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a HackAIthon MVP evidence packet.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--write", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        chain_output = run_diagnostic_chain(args.ticker, sample_size=args.sample_size, timeframe=args.timeframe)
        packet = build_evidence_packet(chain_output)
    except ValueError as exc:
        parser.error(str(exc))
    if args.write:
        _write_json(args.write, packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
