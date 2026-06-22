"""Rich local evidence pack for optional LLM demo explanations."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.engine_universe_gap_analysis import run_engine_universe_gap_analysis
from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY, CREATED_AT, NON_CLAIM_TEXT
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records


PACK_RECORD_IDS = (
    "architecture:scope_boundary",
    "engine-universe-sweep:full-summary",
    "diagnostic-engine:gateway-ready-core",
    "offline-gateway:v0",
    "risk-engine:v3",
    "fine-tune:control-plane",
    "llm:ollama-local-boundary",
)


def _record(record_id: str, record_type: str, title: str, summary: str, content: dict[str, Any], source: str) -> dict:
    return {
        "record_id": record_id,
        "record_type": record_type,
        "title": title,
        "summary": summary,
        "content": content,
        "source_module": source,
        "created_at": CREATED_AT,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
        "read_only": True,
    }


def build_rich_llm_demo_records() -> tuple[dict, ...]:
    """Build read-only records for richer local LLM explanations."""

    gap = run_engine_universe_gap_analysis()
    records = (
        _record(
            "architecture:scope_boundary",
            "claim_boundary",
            "Architecture scope boundary",
            "Local/static diagnostic MVP boundaries for reviewer explanations.",
            {
                "research_only": True,
                "diagnostic_only": True,
                "local_static_only": True,
                "human_review_required": True,
                "no_live_data": True,
                "no_provider_calls": True,
                "no_training": True,
                "no_inference": True,
                "no_benchmark_rerun": True,
            },
            "llm_demo_evidence_pack",
        ),
        _record(
            "engine-universe-sweep:full-summary",
            "engine_run_summary",
            "Engine universe full summary",
            "Latest generated spec universe coverage summary with explicit evidence gaps.",
            {
                "total_discovered": gap["total_specs_discovered"],
                "total_attempted": gap["total_specs_attempted"],
                "completed": gap["completed_count"],
                "skipped": gap["skipped_count"],
                "failed": gap["failed_count"],
                "evidence_coverage_ratio": gap["evidence_coverage_ratio"],
                "diagnostic_distribution": gap["diagnostic_distribution"],
                "skip_reason_distribution": gap["skip_reason_distribution"],
                "family_distribution": gap["family_distribution"],
                "horizon_distribution": gap["horizon_distribution"],
                "generated_spec_universe": True,
                "stronger_claims_require_more_local_evidence": True,
            },
            "engine_universe_gap_analysis",
        ),
        _record(
            "diagnostic-engine:gateway-ready-core",
            "diagnostic_report",
            "Gateway-ready local diagnostic core",
            "Canonical payload handoff into local diagnostic engine with human review.",
            {
                "local_static_diagnostic_subsystem": True,
                "canonical_payload_sections": [
                    "request",
                    "market_bars",
                    "forecast_rows",
                    "model_diagnostics",
                    "scenario_context",
                    "risk_context",
                    "social_context",
                    "metadata",
                ],
                "auto_execution_allowed": False,
                "human_review_required": True,
            },
            "diagnostic_engine",
        ),
        _record(
            "offline-gateway:v0",
            "evidence_packet",
            "Offline Gateway v0",
            "Local CSV, JSONL, or JSON OHLCV intake with explicit-only evidence writes.",
            {
                "local_files_only": True,
                "accepted_formats": ["csv", "jsonl", "json"],
                "writes_require_explicit_store_root": True,
                "no_default_write": True,
                "human_review_required": True,
            },
            "offline_data_gateway",
        ),
        _record(
            "risk-engine:v3",
            "risk_assessment",
            "Risk Engine V3",
            "Diagnostic risk checks for local OHLCV integrity, liquidity, staleness, and evidence consistency.",
            {
                "risk_engine_version": "v3",
                "checks": [
                    "ohlcv_integrity",
                    "liquidity",
                    "volatility_gap",
                    "manipulation_susceptibility",
                    "staleness",
                    "missing_context",
                    "evidence_consistency",
                ],
                "critical_risk_blocks_review_lane": True,
                "human_review_required": True,
            },
            "risk_engine_v3",
        ),
        _record(
            "fine-tune:control-plane",
            "limitation_note",
            "Tuning readiness control plane",
            "Readiness gate only; no model update or blind tuning is performed.",
            {
                "readiness_gate_only": True,
                "requires_local_labeled_rows": True,
                "requires_temporal_validation": True,
                "no_model_update": True,
                "human_review_required": True,
            },
            "model_tuning_readiness",
        ),
        _record(
            "llm:ollama-local-boundary",
            "limitation_note",
            "Optional local Ollama evidence explanation",
            "Local LLM can explain retrieved read-only evidence and must preserve boundaries.",
            {
                "optional_local_experiment": True,
                "expected_model": "qwen3.5:4b",
                "read_only_retrieval": True,
                "no_cloud_api": True,
                "no_mutation": True,
                "human_review_required": True,
            },
            "ollama_llm_experiment",
        ),
    )
    return records


def write_rich_llm_demo_store(*, store_root: str) -> dict:
    """Write the rich demo records only to an explicit local store root."""

    records = build_rich_llm_demo_records()
    write_result = write_llm_readable_records(records=records, store_root=store_root)
    return {
        "pack_status": "written" if write_result.get("write_status") == "written_local_jsonl" else "write_failed",
        "record_count": len(records),
        "record_ids": [record["record_id"] for record in records],
        "write_result": write_result,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_rich_llm_demo_pack_report(result: dict) -> str:
    """Render a compact evidence pack report."""

    lines = [
        "# Rich LLM Demo Evidence Pack",
        "",
        f"Pack status: {result.get('pack_status')}",
        f"Record count: {result.get('record_count')}",
        "Record IDs:",
        *[f"- {record_id}" for record_id in result.get("record_ids", [])],
        "",
        "Boundary:",
        "Writes require an explicit local store root; no files are written by default.",
        "Records are read-only local evidence for human-reviewed explanations.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    write_result = result.get("write_result") if isinstance(result.get("write_result"), dict) else {}
    if write_result:
        lines.extend(["", f"Write status: {write_result.get('write_status')}"])
        if write_result.get("errors"):
            lines.extend(["Errors:", *[f"- {error}" for error in write_result["errors"]]])
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or write a rich local LLM demo evidence pack.")
    parser.add_argument("--write-store", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.write_store:
        result = write_rich_llm_demo_store(store_root=args.write_store)
    else:
        records = build_rich_llm_demo_records()
        result = {
            "pack_status": "records_built",
            "record_count": len(records),
            "record_ids": [record["record_id"] for record in records],
            "records": records,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
    if args.format == "report":
        print(render_rich_llm_demo_pack_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("pack_status") in {"records_built", "written"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
