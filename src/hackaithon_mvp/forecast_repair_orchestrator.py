"""Forecast repair orchestration for robust selective local forecast mode."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.deoverlapped_forecast_dataset import build_deoverlapped_forecast_dataset
from src.hackaithon_mvp.forecast_60pct_release_gate import evaluate_60pct_release_gate
from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy, load_forecast_accuracy_rows
from src.hackaithon_mvp.forecast_data_repair_audit import audit_forecast_dataset_integrity
from src.hackaithon_mvp.fresh_validation_protocol import build_nested_walk_forward_protocol, build_three_way_time_split
from src.hackaithon_mvp.full_eligible_model_trainer import run_full_eligible_model_training
from src.hackaithon_mvp.full_engine_universe_runner import run_engine_universe_with_generated_evidence
from src.hackaithon_mvp.local_training_dataset_builder import (
    FEATURE_BLOCKS,
    build_supervised_direction_dataset,
    load_discovered_ohlcv_rows,
)
from src.hackaithon_mvp.model_run_evidence_materializer import materialize_engine_evidence_from_training_run
from src.hackaithon_mvp.robust_forecast_slice_gate import build_forecast_allowed_slices
from src.hackaithon_mvp.selective_forecast_mode import (
    build_selective_forecast_policy,
    evaluate_selective_forecast_policy,
)


STATUS_IMPROVED = "forecast_mode_improved"
STATUS_ABSTAINS = "forecast_mode_abstains_most_slices"
STATUS_NOT_BETTER = "forecast_mode_not_better_than_random"
STATUS_BLOCKED = "forecast_mode_blocked_by_data_quality"
CLAIM_BOUNDARY = {
    "local_forecast_repair_only": True,
    "writes_only_under_tmp_forecast_repair": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_benchmark_rerun": True,
    "no_market_action_output": True,
    "post_hoc_repair_validation": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast repair mode reports accuracy with coverage and abstains when evidence is weak."


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_forecast_repair") for part in root.parts):
        raise ValueError("output_root must be .tmp_forecast_repair or a child path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    omit = {
        "rows",
        "retained_rows",
        "abstained_rows_payload",
        "accuracy_evaluation",
        "train_rows",
        "validation_rows",
        "holdout_rows",
    }
    output = {}
    for key, value in result.items():
        if key in omit:
            if isinstance(value, list):
                output[f"{key}_count"] = len(value)
            continue
        if isinstance(value, dict):
            output[key] = _public_result(value)
        elif isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            output[key] = [_public_result(item) for item in value[:50]]
        else:
            output[key] = value
    return output


def _metric_summary(rows: list[dict]) -> dict[str, Any]:
    accuracy = evaluate_forecast_accuracy(rows)
    directional = accuracy["global"]["directional"]
    baseline = accuracy.get("baseline_comparison") or {}
    return {
        "rows": len(rows),
        "accuracy": directional.get("accuracy"),
        "balanced_accuracy": directional.get("balanced_accuracy"),
        "mcc": directional.get("mcc"),
        "wilson_accuracy_interval": directional.get("wilson_accuracy_interval"),
        "random_baseline": baseline.get("random_50_50_baseline_accuracy"),
        "majority_baseline": baseline.get("majority_class_baseline_accuracy"),
        "previous_direction_baseline": baseline.get("previous_direction_baseline_accuracy"),
        "beats_random": _beats(directional.get("balanced_accuracy"), baseline.get("random_50_50_baseline_accuracy")),
        "beats_majority": _beats(directional.get("balanced_accuracy"), baseline.get("majority_class_baseline_accuracy")),
        "beats_previous_direction": _beats(directional.get("balanced_accuracy"), baseline.get("previous_direction_baseline_accuracy")),
    }


def _beats(value: Any, baseline: Any) -> bool:
    return isinstance(value, (int, float)) and isinstance(baseline, (int, float)) and float(value) > float(baseline)


def _best_group(groups: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidates = []
    for key, value in groups.items():
        score = value.get("balanced_accuracy")
        rows = value.get("coverage_count") or value.get("rows") or 0
        if isinstance(score, (int, float)):
            candidates.append({"slice": key, **value, "_rows": rows})
    if not candidates:
        return None
    candidates.sort(key=lambda item: (float(item["balanced_accuracy"]), int(item.get("_rows") or 0)), reverse=True)
    selected = dict(candidates[0])
    selected.pop("_rows", None)
    return selected


def _status(selective: dict[str, Any], audit: dict[str, Any]) -> str:
    retained_rows = len(selective.get("retained_rows") or [])
    normalized = int(selective.get("normalized_rows") or 0)
    coverage = retained_rows / normalized if normalized else 0.0
    bacc = selective.get("global_retained_balanced_accuracy")
    random_baseline = (selective.get("baselines_on_retained_rows") or {}).get("random_50_50")
    if audit.get("leakage_warning") and retained_rows == 0:
        return STATUS_BLOCKED
    if not _beats(bacc, random_baseline):
        return STATUS_NOT_BETTER
    if coverage < 0.10:
        return STATUS_ABSTAINS
    return STATUS_IMPROVED


def _copy_retained_evidence(root: Path, retained_rows: list[dict]) -> dict[str, Any]:
    evidence_root = root / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    retained_path = evidence_root / "retained_forecast_rows.jsonl"
    _write_jsonl(retained_path, retained_rows)
    return {
        "materialization_status": "completed" if retained_rows else "no_retained_rows",
        "evidence_root": str(evidence_root),
        "retained_forecast_rows": str(retained_path),
        "retained_row_count": len(retained_rows),
    }


def _load_or_train_rows(
    *,
    root: Path,
    max_workers: int,
    max_models: int | None,
    min_slice_rows: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    existing = root / "forecast_actual_rows.jsonl"
    if existing.exists():
        return {"dataset_status": "reused_existing_forecast_rows"}, load_forecast_accuracy_rows(str(existing)), {
            "training_run_status": "reused_existing_forecast_rows",
            "forecast_actual_output": str(existing),
        }

    bars = list(load_discovered_ohlcv_rows(repo_root="."))
    dataset = build_supervised_direction_dataset(bars, feature_blocks=FEATURE_BLOCKS)
    dataset_rows = list(dataset.get("rows") or [])
    dataset_path = root / "training_dataset.jsonl"
    _write_jsonl(dataset_path, dataset_rows)
    _write_json(root / "training_dataset_summary.json", {key: value for key, value in dataset.items() if key != "rows"})
    if dataset.get("dataset_status") != "ready":
        return dataset, [], {"training_run_status": "blocked_by_dataset_status"}

    training = run_full_eligible_model_training(
        dataset_path=str(dataset_path),
        output_root=str(root),
        max_models=max_models,
        max_workers=max_workers,
        timeout_seconds_per_model=60,
        clean_slices_only=True,
        deoverlap=True,
        prioritize_horizons=(1, 5, 10, 20),
        min_slice_rows=min_slice_rows,
        selection_metric="holdout_balanced_accuracy",
    )
    forecast_path = Path(training.get("forecast_actual_output") or root / "forecast_actual_rows.jsonl")
    rows = load_forecast_accuracy_rows(str(forecast_path)) if forecast_path.exists() else []
    return {key: value for key, value in dataset.items() if key != "rows"}, rows, training


def run_forecast_repair_pipeline(
    *,
    output_root: str,
    max_workers: int = 1,
    max_models: int | None = 300,
    min_slice_rows: int = 300,
) -> dict:
    """Run the local forecast repair pipeline."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    started = time.monotonic()
    root = _output_root(output_root)

    dataset, forecast_rows, training = _load_or_train_rows(
        root=root,
        max_workers=max_workers,
        max_models=max_models,
        min_slice_rows=min_slice_rows,
    )
    if not forecast_rows:
        result = {
            "forecast_mode_status": STATUS_BLOCKED,
            "output_root": str(root),
            "dataset": dataset,
            "training": training,
            "rows_before_repair": 0,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
        _write_json(root / "forecast_repair_summary.json", _public_result(result))
        return result

    _write_jsonl(root / "forecast_actual_rows.jsonl", forecast_rows)
    audit = audit_forecast_dataset_integrity(forecast_rows)
    _write_json(root / "forecast_data_repair_audit.json", audit)
    deoverlap = build_deoverlapped_forecast_dataset(forecast_rows)
    clean_rows = list(deoverlap.get("rows") or [])
    clean_path = root / "deoverlapped_rows.jsonl"
    _write_jsonl(clean_path, clean_rows)
    _write_json(root / "deoverlapped_dataset_summary.json", {key: value for key, value in deoverlap.items() if key != "rows"})

    split = build_three_way_time_split(clean_rows)
    walk_forward = build_nested_walk_forward_protocol(clean_rows)
    _write_json(root / "fresh_validation_protocol.json", _public_result(split))
    _write_json(root / "nested_walk_forward_protocol.json", walk_forward)

    gate = build_forecast_allowed_slices(clean_rows, min_rows=min_slice_rows)
    _write_json(root / "robust_slice_gate.json", gate)
    policy = build_selective_forecast_policy(clean_rows, min_rows=min_slice_rows)
    selective = evaluate_selective_forecast_policy(clean_rows, policy)
    retained_rows = list(selective.get("retained_rows") or [])
    retained_path = root / "retained_forecast_rows.jsonl"
    _write_jsonl(retained_path, retained_rows)
    _write_json(root / "selective_forecast_policy.json", _public_result(policy))
    _write_json(root / "selective_forecast_evaluation.json", _public_result(selective))

    materialized = materialize_engine_evidence_from_training_run(run_root=str(root), evidence_root=str(root / "evidence"))
    retained_evidence = _copy_retained_evidence(root, retained_rows)
    if retained_rows:
        shutil.copyfile(retained_path, root / "evidence" / "forecast_actual_rows.jsonl")
    try:
        engine = run_engine_universe_with_generated_evidence(
            evidence_root=str(root / "evidence"),
            output_root=str(root / "engine_sweep"),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        engine = {
            "engine_universe_run_status": "skipped_after_retained_evidence",
            "skip_reason": f"{type(exc).__name__}: {exc}",
            "completed_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
        }

    retained_metric = _metric_summary(retained_rows)
    status = _status(selective, audit)
    broad_claim_allowed = bool(
        retained_rows
        and retained_metric.get("beats_random")
        and retained_metric.get("beats_majority")
        and retained_metric.get("beats_previous_direction")
        and not audit.get("leakage_warning")
    )
    forecast_60pct_gate = evaluate_60pct_release_gate(
        {
            "retained_holdout_accuracy": selective.get("global_retained_accuracy"),
            "retained_holdout_balanced_accuracy": selective.get("global_retained_balanced_accuracy"),
            "retained_holdout_mcc": selective.get("mcc"),
            "retained_rows": len(retained_rows),
            "retained_coverage": selective.get("forecast_coverage"),
            "retained_baselines": selective.get("baselines_on_retained_rows"),
            "retained_forecast_rows": retained_rows,
            "audit": audit,
        }
    )
    best_ticker = _best_group(selective.get("by_ticker") or {})
    best_horizon = _best_group(selective.get("by_horizon") or {})
    result = {
        "forecast_mode_status": status,
        "output_root": str(root),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "max_workers": max_workers,
        "max_models": max_models,
        "min_slice_rows": min_slice_rows,
        "dataset": dataset,
        "training": training,
        "rows_before_repair": len(forecast_rows),
        "duplicate_keys_removed": deoverlap.get("dropped_duplicate_rows"),
        "overlapping_rows_removed": deoverlap.get("dropped_overlap_rows"),
        "clean_rows_retained": deoverlap.get("retained_rows"),
        "audit": audit,
        "deoverlapped_dataset": {key: value for key, value in deoverlap.items() if key != "rows"},
        "fresh_validation_protocol": _public_result(split),
        "nested_walk_forward_protocol": walk_forward,
        "robust_slice_gate": gate,
        "selective_forecast_policy": _public_result(policy),
        "selective_forecast_evaluation": _public_result(selective),
        "retained_forecast_rows_output": str(retained_path),
        "retained_evidence": retained_evidence,
        "evidence_materialization": materialized,
        "engine_universe": engine,
        "retained_metrics": retained_metric,
        "allowed_forecast_slices": gate.get("allowed_slice_count"),
        "abstained_slices": gate.get("abstained_slice_count"),
        "retained_forecast_coverage": selective.get("forecast_coverage"),
        "retained_accuracy": selective.get("global_retained_accuracy"),
        "retained_balanced_accuracy": selective.get("global_retained_balanced_accuracy"),
        "retained_mcc": selective.get("mcc"),
        "baselines_on_retained_rows": selective.get("baselines_on_retained_rows"),
        "best_allowed_ticker": best_ticker,
        "best_allowed_horizon": best_horizon,
        "forecast_release_status": forecast_60pct_gate.get("forecast_release_status"),
        "forecast_60pct_release_gate": forecast_60pct_gate,
        "forecast_release_allowed": forecast_60pct_gate.get("forecast_release_allowed"),
        "broad_performance_claim_allowed": bool(broad_claim_allowed and forecast_60pct_gate.get("broad_performance_claim_allowed")),
        "validation_protocol_status": "post_hoc_repair_validation",
        "truly_fresh_holdout_exists": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "forecast_repair_summary.json", _public_result(result))
    return result


def render_forecast_repair_report(result: dict) -> str:
    """Render a compact forecast repair report."""

    retained = result.get("retained_metrics") or {}
    baselines = result.get("baselines_on_retained_rows") or {}
    engine = result.get("engine_universe") or {}
    lines = [
        "# Forecast Repair Orchestrator",
        "",
        f"Forecast-mode status: {result.get('forecast_mode_status')}",
        f"Output root: {result.get('output_root')}",
        f"Elapsed seconds: {result.get('elapsed_seconds')}",
        f"Rows before repair: {result.get('rows_before_repair')}",
        f"Duplicate keys removed: {result.get('duplicate_keys_removed')}",
        f"Overlapping rows removed: {result.get('overlapping_rows_removed')}",
        f"Clean rows retained: {result.get('clean_rows_retained')}",
        f"Allowed forecast slices: {result.get('allowed_forecast_slices')}",
        f"Abstained slices: {result.get('abstained_slices')}",
        f"Retained forecast coverage: {result.get('retained_forecast_coverage')}",
        f"Retained accuracy: {result.get('retained_accuracy')}",
        f"Retained balanced accuracy: {result.get('retained_balanced_accuracy')}",
        f"Retained MCC: {result.get('retained_mcc')}",
        "",
        "Baselines on retained rows:",
        f"- random 50/50: {baselines.get('random_50_50')}",
        f"- majority class: {baselines.get('majority_class')}",
        f"- previous direction: {baselines.get('previous_direction')}",
        "",
        "Baseline comparisons:",
        f"- beats random: {retained.get('beats_random')}",
        f"- beats majority: {retained.get('beats_majority')}",
        f"- beats previous direction: {retained.get('beats_previous_direction')}",
        "",
        f"60 percent forecast release status: {result.get('forecast_release_status')}",
        f"60 percent forecast release allowed: {result.get('forecast_release_allowed')}",
        "",
        "Engine universe:",
        f"- status: {engine.get('engine_universe_run_status')}",
        f"- completed: {engine.get('completed_count')}",
        f"- skipped: {engine.get('skipped_count')}",
        f"- failed: {engine.get('failed_count')}",
        "",
        f"Broad performance claim allowed: {result.get('broad_performance_claim_allowed')}",
        f"Validation protocol status: {result.get('validation_protocol_status')}",
        f"Truly fresh holdout exists: {result.get('truly_fresh_holdout_exists')}",
        "",
        "Boundary:",
        "Selective forecast mode reports coverage with accuracy and abstains weak slices for human review.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local forecast repair pipeline.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--max-models", type=int, default=300)
    parser.add_argument("--min-slice-rows", type=int, default=300)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_forecast_repair_pipeline(
        output_root=args.output_root,
        max_workers=args.max_workers,
        max_models=args.max_models,
        min_slice_rows=args.min_slice_rows,
    )
    public = _public_result(result)
    if args.format == "report":
        print(render_forecast_repair_report(public), end="")
    else:
        print(json.dumps(public, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
