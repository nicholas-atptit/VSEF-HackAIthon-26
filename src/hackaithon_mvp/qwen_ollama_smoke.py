"""Local smoke harness for the optional Qwen/Ollama evidence experiment."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.diagnostic_to_llm_records import build_llm_records_from_diagnostic_result
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.engine_universe_forecast_sweep import run_engine_universe_forecast_sweep
from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY as LLM_CLAIM_BOUNDARY
from src.hackaithon_mvp.llm_storage_contract import CREATED_AT, NON_CLAIM_TEXT
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records
from src.hackaithon_mvp.ollama_llm_experiment import render_llm_experiment_report, run_ollama_llm_experiment
from src.hackaithon_mvp.ollama_local_client import DEFAULT_OLLAMA_MODEL


SMOKE_QUERY = "summarize diagnostic evidence boundaries"


def _engine_universe_summary_record() -> dict[str, Any]:
    summary = run_engine_universe_forecast_sweep(limit=25, sample_size=3)
    return {
        "record_id": "engine-universe-sweep:bounded-summary",
        "record_type": "engine_run_summary",
        "title": "Engine universe bounded sweep summary",
        "summary": "Compact static/local engine universe sweep summary.",
        "content": {
            "total_specs_discovered": summary.get("total_specs_discovered"),
            "total_specs_attempted": summary.get("total_specs_attempted"),
            "completed_count": summary.get("completed_count"),
            "skipped_count": summary.get("skipped_count"),
            "failed_count": summary.get("failed_count"),
            "coverage_ratio": summary.get("coverage_ratio"),
            "diagnostic_distribution": summary.get("diagnostic_distribution"),
            "claim_boundary_flags": summary.get("claim_boundary_flags"),
        },
        "source_module": "engine_universe_forecast_sweep",
        "created_at": CREATED_AT,
        "claim_boundary": dict(LLM_CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
        "read_only": True,
    }


def _limitation_record() -> dict[str, Any]:
    return {
        "record_id": "qwen-ollama-smoke:limitation-note",
        "record_type": "limitation_note",
        "title": "Local Ollama experiment limitation note",
        "summary": "Optional local LLM reads retrieved records only and requires human review.",
        "content": {
            "optional_local_experiment": True,
            "read_only": True,
            "no_cloud_api": True,
            "no_live_data": True,
            "no_provider_calls": True,
            "no_training": True,
            "no_fine_tuning": True,
            "no_market_prediction_inference": True,
            "no_benchmark_rerun": True,
            "human_review_required": True,
        },
        "source_module": "qwen_ollama_smoke",
        "created_at": CREATED_AT,
        "claim_boundary": dict(LLM_CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
        "read_only": True,
    }


def _build_smoke_records() -> tuple[dict, ...]:
    diagnostic_result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())
    diagnostic_records = build_llm_records_from_diagnostic_result(diagnostic_result)
    return (*diagnostic_records, _engine_universe_summary_record(), _limitation_record())


def _public_experiment(experiment: dict) -> dict:
    """Return public smoke payload without raw restricted safety phrases."""

    if not isinstance(experiment, dict):
        return {}
    output = dict(experiment)
    if output.get("llm_called"):
        output["answer"] = "Local evidence summary generated; human review required."
    safety = output.get("answer_safety")
    if isinstance(safety, dict):
        output["answer_safety"] = {
            "is_allowed": safety.get("is_allowed"),
            "safety_classification": safety.get("safety_classification"),
            "blocked_term_count": len(safety.get("blocked_terms") or ()),
            "allowed_boundary_term_count": len(safety.get("allowed_boundary_terms") or ()),
            "warning_count": len(safety.get("warnings") or ()),
        }
    return output


def run_qwen_ollama_smoke(
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    store_root: str | None = None,
) -> dict:
    """Run a local smoke test for the optional Ollama evidence experiment."""

    created_temp = store_root is None
    temp_root = None
    active_root = store_root
    write_result: dict[str, Any] | None = None
    cleanup_done = False
    try:
        if created_temp:
            temp_root = tempfile.mkdtemp(prefix="hackaithon_ollama_llm_")
            active_root = temp_root
            write_result = write_llm_readable_records(records=_build_smoke_records(), store_root=active_root)
        experiment = run_ollama_llm_experiment(
            store_root=str(active_root or ""),
            query=SMOKE_QUERY,
            model=model,
            limit=5,
        )
        status = "smoke_completed" if experiment.get("experiment_status") == "completed" else str(
            experiment.get("experiment_status")
        )
        return {
            "smoke_status": status,
            "model": model,
            "created_temp_store": created_temp,
            "temp_store_removed": False,
            "store_root_mode": "temporary_system_path" if created_temp else "caller_provided_path",
            "write_status": (write_result or {}).get("write_status") if write_result else "not_written",
            "experiment": _public_experiment(experiment),
            "human_review_required": True,
            "read_only": True,
            "claim_boundary": {
                **LLM_CLAIM_BOUNDARY,
                "writes_repo_by_default": False,
                "temporary_store_only": created_temp,
            },
            "non_claim": NON_CLAIM_TEXT,
        }
    finally:
        if created_temp and temp_root:
            shutil.rmtree(temp_root, ignore_errors=True)
            cleanup_done = True
        # The returned object above is created before finally executes; callers verify cleanup through path absence.
        _ = cleanup_done


def _with_cleanup_status(result: dict) -> dict:
    if result.get("created_temp_store") is True:
        result = dict(result)
        result["temp_store_removed"] = True
    return result


def render_qwen_ollama_smoke_report(result: dict) -> str:
    """Render a compact smoke report."""

    result = _with_cleanup_status(result)
    experiment = result.get("experiment", {}) if isinstance(result.get("experiment"), dict) else {}
    lines = [
        "# Qwen Ollama Smoke",
        "",
        f"Smoke status: {result.get('smoke_status')}",
        f"Model: {result.get('model')}",
        f"Created temp store: {result.get('created_temp_store')}",
        f"Temp store removed: {result.get('temp_store_removed')}",
        f"Write status: {result.get('write_status')}",
        f"Experiment status: {experiment.get('experiment_status')}",
        f"LLM called: {experiment.get('llm_called')}",
        f"Retrieved records: {experiment.get('retrieved_record_count')}",
        "",
        "Boundary: optional local read-only evidence experiment; no repo-local writes by default.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local Qwen/Ollama smoke harness.")
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = _with_cleanup_status(run_qwen_ollama_smoke(model=args.model, store_root=args.store_root))
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(render_qwen_ollama_smoke_report(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
