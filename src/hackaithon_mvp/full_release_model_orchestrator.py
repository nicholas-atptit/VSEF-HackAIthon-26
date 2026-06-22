"""Orchestrate the local full model/evidence generation pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.full_eligible_model_trainer import (
    render_full_eligible_model_training_report,
    run_full_eligible_model_training,
)
from src.hackaithon_mvp.full_engine_universe_runner import run_engine_universe_with_generated_evidence
from src.hackaithon_mvp.full_model_run_planner import build_full_model_run_plan
from src.hackaithon_mvp.local_training_dataset_builder import (
    build_supervised_direction_dataset,
    load_discovered_ohlcv_rows,
    render_training_dataset_report,
)
from src.hackaithon_mvp.model_run_evidence_materializer import materialize_engine_evidence_from_training_run
from src.hackaithon_mvp.optional_provider_data_fetch import run_optional_provider_data_fetch
from src.hackaithon_mvp.release_accuracy_report import build_release_accuracy_report


MIN_DATASET_ROWS = 1_000
CLAIM_BOUNDARY = {
    "local_full_pipeline": True,
    "writes_only_under_output_root": True,
    "no_live_data_by_default": True,
    "provider_fetch_requires_explicit_flag": True,
    "no_model_binaries_committed": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Full local release model pipeline; generated outputs remain untracked local artifacts."


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_full_model_run") for part in root.parts):
        raise ValueError("output_root must be .tmp_full_model_run or a child path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _status(training: dict, engine: dict, dataset: dict) -> str:
    if dataset.get("dataset_status") != "ready":
        return "blocked_by_data_unavailability"
    if int(training.get("trained_model_specs") or 0) == 0:
        return "completed_no_trainable_data"
    if int(engine.get("skipped_count") or 0) > 0:
        return "completed_partial_due_to_dependencies"
    return "completed_with_generated_evidence"


def run_full_release_model_pipeline(
    *,
    output_root: str,
    allow_provider_fetch: bool = False,
    max_tickers: int | None = None,
    max_models: int | None = None,
    max_workers: int = 1,
) -> dict:
    """Run the full local training/tuning/evidence generation pipeline."""

    root = _output_root(output_root)
    plan = build_full_model_run_plan(repo_root=".", max_tickers=max_tickers)
    bars = list(load_discovered_ohlcv_rows(repo_root=".", max_tickers=max_tickers))
    dataset = build_supervised_direction_dataset(bars)
    provider_result = None
    if dataset.get("dataset_status") != "ready" or int(dataset.get("dataset_row_count") or 0) < MIN_DATASET_ROWS:
        provider_result = run_optional_provider_data_fetch(
            output_path=str(root / "provider_bars.jsonl"),
            allow_provider_fetch=allow_provider_fetch,
        )
        if provider_result.get("row_count"):
            # Provider implementation is currently contract-only; this branch is for future compatibility.
            dataset = build_supervised_direction_dataset(bars)

    dataset_path = root / "training_dataset.jsonl"
    _write_jsonl(dataset_path, dataset.get("rows", []))
    dataset_public = {key: value for key, value in dataset.items() if key != "rows"}
    _write_json(root / "training_dataset_summary.json", dataset_public)

    if dataset.get("dataset_status") != "ready" or int(dataset.get("dataset_row_count") or 0) < MIN_DATASET_ROWS:
        training = {
            "training_run_status": "completed_no_trainable_data",
            "dataset_path": str(dataset_path),
            "dataset_row_count": dataset.get("dataset_row_count"),
            "attempted_model_specs": 0,
            "trained_model_specs": 0,
            "tuned_model_specs": 0,
            "skipped_model_specs": 0,
            "forecast_actual_output": str(root / "forecast_actual_rows.jsonl"),
            "skipped_models": [{"skip_reason": "insufficient_local_supervised_rows"}],
        }
        evidence = {
            "materialization_status": "no_evidence_records",
            "static_evidence_record_count": 0,
            "dependency_result_count": 0,
            "forecast_row_count": 0,
        }
        engine = {
            "engine_universe_run_status": "not_run_no_generated_evidence",
            "completed_count": 0,
            "skipped_count": 77_850,
            "completed_improvement": -120,
            "skip_reason_distribution": {"insufficient_local_supervised_rows": 77_850},
        }
        accuracy = build_release_accuracy_report(input_path=None)
    else:
        training = run_full_eligible_model_training(
            dataset_path=str(dataset_path),
            output_root=str(root),
            max_models=max_models,
            max_workers=max_workers,
            timeout_seconds_per_model=120,
        )
        evidence = materialize_engine_evidence_from_training_run(
            run_root=str(root),
            evidence_root=str(root / "evidence"),
        )
        engine = run_engine_universe_with_generated_evidence(
            evidence_root=str(root / "evidence"),
            output_root=str(root / "engine_sweep"),
        )
        accuracy = build_release_accuracy_report(
            input_path=str(root / "forecast_actual_rows.jsonl"),
            tuning_output_path=str(root / "tuning_report.json"),
        )

    result = {
        "pipeline_status": _status(training, engine, dataset),
        "output_root": str(root),
        "provider_fetch_used": bool(provider_result and provider_result.get("row_count")),
        "provider_fetch_result": provider_result,
        "plan": plan,
        "dataset": dataset_public,
        "training": training,
        "release_accuracy": accuracy,
        "evidence_materialization": evidence,
        "engine_universe": engine,
        "coverage_improvement": {
            "previous_completed": engine.get("previous_completed_count", 120),
            "new_completed": engine.get("completed_count", 0),
            "completed_improvement": engine.get("completed_improvement"),
            "previous_skipped": engine.get("previous_skipped_count", 77_730),
            "new_skipped": engine.get("skipped_count"),
            "skipped_reduction": engine.get("skipped_reduction"),
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "full_release_model_pipeline_summary.json", result)
    return result


def render_full_release_model_pipeline_report(result: dict) -> str:
    """Render a compact full pipeline report."""

    training = result.get("training") or {}
    accuracy = result.get("release_accuracy") or {}
    engine = result.get("engine_universe") or {}
    dataset = result.get("dataset") or {}
    lines = [
        "# Full Release Model Pipeline",
        "",
        f"Pipeline status: {result.get('pipeline_status')}",
        f"Output root: {result.get('output_root')}",
        f"Provider fetch used: {result.get('provider_fetch_used')}",
        "",
        "Dataset:",
        f"- status: {dataset.get('dataset_status')}",
        f"- rows: {dataset.get('dataset_row_count')}",
        f"- tickers: {dataset.get('ticker_count')}",
        "",
        "Training/tuning:",
        f"- attempted model specs: {training.get('attempted_model_specs')}",
        f"- trained model specs: {training.get('trained_model_specs')}",
        f"- tuned model specs: {training.get('tuned_model_specs')}",
        f"- skipped model specs: {training.get('skipped_model_specs')}",
        "",
        "Release accuracy:",
        f"- status: {accuracy.get('release_accuracy_status')}",
        f"- evaluated rows: {accuracy.get('evaluated_row_count')}",
        f"- directional accuracy: {accuracy.get('global_directional_accuracy')}",
        f"- balanced accuracy: {accuracy.get('global_balanced_accuracy')}",
        "",
        "Generated engine universe:",
        f"- completed specs: {engine.get('completed_count')}",
        f"- skipped specs: {engine.get('skipped_count')}",
        f"- completed improvement: {engine.get('completed_improvement')}",
        f"- skipped reduction: {engine.get('skipped_reduction')}",
        "",
        "Top remaining skip reasons:",
    ]
    skips = engine.get("skip_reason_distribution") or {}
    lines.extend([f"- {key}: {value}" for key, value in list(skips.items())[:8]] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Generated outputs remain local and untracked under the explicit output root.",
            "Metrics are computed only from generated forecast-vs-actual rows with local actual outcomes.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full local release model/evidence pipeline.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--allow-provider-fetch", action="store_true")
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--max-models", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_full_release_model_pipeline(
        output_root=args.output_root,
        allow_provider_fetch=args.allow_provider_fetch,
        max_tickers=args.max_tickers,
        max_models=args.max_models,
        max_workers=args.max_workers,
    )
    if args.format == "report":
        print(render_full_release_model_pipeline_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
