"""Bounded local accuracy maximization pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.accuracy_maximization_planner import build_accuracy_maximization_plan
from src.hackaithon_mvp.diagnostic_ensemble_selector import evaluate_ensemble_candidates
from src.hackaithon_mvp.final_holdout_evaluator import build_final_holdout_split, evaluate_final_holdout
from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
)
from src.hackaithon_mvp.forecast_signal_sanity_audit import run_forecast_signal_sanity_audit
from src.hackaithon_mvp.full_eligible_model_trainer import run_full_eligible_model_training
from src.hackaithon_mvp.full_engine_universe_runner import run_engine_universe_with_generated_evidence
from src.hackaithon_mvp.local_training_dataset_builder import (
    FEATURE_BLOCKS,
    build_supervised_direction_dataset,
    load_discovered_ohlcv_rows,
)
from src.hackaithon_mvp.model_champion_selector import select_champions_by_slice
from src.hackaithon_mvp.model_run_evidence_materializer import materialize_engine_evidence_from_training_run
from src.hackaithon_mvp.purged_walk_forward_validation import run_walk_forward_folds
from src.hackaithon_mvp.release_baseline_sanity_audit import audit_release_baselines
from src.hackaithon_mvp.selective_prediction_gate import tune_confidence_gate


CLAIM_BOUNDARY = {
    "local_accuracy_maximization_only": True,
    "writes_only_under_output_root": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_benchmark_rerun": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Accuracy maximization is local research diagnostics; final holdout metrics must be reported with baselines and coverage."


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_accuracy_maximization") for part in root.parts):
        raise ValueError("output_root must be .tmp_accuracy_maximization or a child path")
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


def _flip_row(row: dict) -> dict:
    output = dict(row)
    direction = output.get("predicted_direction")
    if direction == UP:
        output["predicted_direction"] = DOWN
    elif direction == DOWN:
        output["predicted_direction"] = UP
    probability = output.get("predicted_probability")
    if isinstance(probability, (int, float)):
        output["predicted_probability"] = round(1.0 - float(probability), 12)
    output["accuracy_maximization_policy"] = "fixed_flip_from_validation_audit"
    return output


def _apply_flip(rows: list[dict], *, enabled: bool) -> list[dict]:
    return [_flip_row(row) for row in rows] if enabled else [dict(row) for row in rows]


def _public_result(result: dict) -> dict:
    omit = {"rows", "scored_rows", "accuracy_evaluation"}
    output = {}
    for key, value in result.items():
        if key in omit:
            continue
        if isinstance(value, dict):
            output[key] = _public_result(value)
        else:
            output[key] = value
    return output


def _metric_summary(rows: list[dict]) -> dict:
    result = evaluate_forecast_accuracy(rows)
    directional = result["global"]["directional"]
    baseline = result.get("baseline_comparison") or {}
    return {
        "evaluated_rows": result.get("evaluated_row_count"),
        "accuracy": directional.get("accuracy"),
        "balanced_accuracy": directional.get("balanced_accuracy"),
        "mcc": directional.get("mcc"),
        "wilson_accuracy_interval": directional.get("wilson_accuracy_interval"),
        "random_baseline": baseline.get("random_50_50_baseline_accuracy"),
        "majority_baseline": baseline.get("majority_class_baseline_accuracy"),
        "previous_direction_baseline": baseline.get("previous_direction_baseline_accuracy"),
    }


def _best_group(groups: dict[str, dict]) -> dict | None:
    candidates = []
    for key, value in groups.items():
        if not isinstance(value, dict):
            continue
        score = value.get("balanced_accuracy")
        if isinstance(score, (int, float)):
            candidates.append({"slice": key, **value})
    if not candidates:
        return None
    candidates.sort(key=lambda item: (float(item["balanced_accuracy"]), int(item.get("coverage_count") or item.get("rows") or 0)), reverse=True)
    return candidates[0]


def run_accuracy_maximization_pipeline(
    *,
    output_root: str,
    max_workers: int = 1,
    max_models: int | None = None,
    max_runtime_minutes: int = 60,
    optimize_for: str = "balanced_accuracy",
) -> dict:
    """Run the bounded local accuracy maximization pipeline."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if max_runtime_minutes < 1:
        raise ValueError("max_runtime_minutes must be positive")
    if optimize_for not in {"balanced_accuracy", "directional_accuracy", "mcc"}:
        raise ValueError("optimize_for must be balanced_accuracy, directional_accuracy, or mcc")
    started = time.monotonic()
    root = _output_root(output_root)

    plan = build_accuracy_maximization_plan(repo_root=".")
    bars = list(load_discovered_ohlcv_rows(repo_root="."))
    dataset = build_supervised_direction_dataset(bars, feature_blocks=FEATURE_BLOCKS)
    dataset_path = root / "training_dataset.jsonl"
    _write_jsonl(dataset_path, dataset.get("rows", []))
    dataset_public = {key: value for key, value in dataset.items() if key != "rows"}
    _write_json(root / "training_dataset_summary.json", dataset_public)

    if dataset.get("dataset_status") != "ready":
        result = {
            "pipeline_status": "blocked_by_data_unavailability",
            "output_root": str(root),
            "plan": plan,
            "dataset": dataset_public,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
        _write_json(root / "accuracy_maximization_summary.json", _public_result(result))
        return result

    remaining_seconds = max(max_runtime_minutes * 60 - int(time.monotonic() - started), 60)
    training = run_full_eligible_model_training(
        dataset_path=str(dataset_path),
        output_root=str(root),
        max_models=max_models,
        max_workers=max_workers,
        timeout_seconds_per_model=min(120, max(30, remaining_seconds // max(int(max_models or 1), 1))),
    )
    forecast_path = root / "forecast_actual_rows.jsonl"
    forecast_rows = load_forecast_accuracy_rows(str(forecast_path)) if forecast_path.exists() else []
    holdout_split = build_final_holdout_split(forecast_rows, holdout_fraction=0.20)
    train_validation_rows = list(holdout_split.get("train_validation_rows") or [])
    holdout_rows = list(holdout_split.get("holdout_rows") or [])

    signal_audit = run_forecast_signal_sanity_audit(train_validation_rows)
    baseline_audit = audit_release_baselines(train_validation_rows)
    walk_forward = run_walk_forward_folds(train_validation_rows, n_folds=3, horizon_steps=40)
    flip_diagnostic = signal_audit.get("prediction_flip_rescue") or {}
    flip_enabled = bool(
        flip_diagnostic.get("possible_label_polarity_mismatch")
        or flip_diagnostic.get("flipped_predictions_materially_outperform_original")
    )
    train_validation_policy_rows = _apply_flip(train_validation_rows, enabled=flip_enabled)
    holdout_policy_input_rows = _apply_flip(holdout_rows, enabled=flip_enabled)

    confidence = tune_confidence_gate(train_validation_policy_rows, metric=optimize_for)
    selected_confidence = confidence.get("selected_threshold") if confidence.get("tuning_status") == "completed" else None
    ensemble = evaluate_ensemble_candidates(train_validation_policy_rows)
    champion_selection = select_champions_by_slice(training.get("model_results", []))

    selected_policy = {
        "policy_id": "accuracy_maximization_fixed_validation_policy",
        "rows_are_holdout": True,
        "flip_predictions": False,
        "confidence_threshold": selected_confidence,
        "validation_flip_policy_applied_before_holdout": flip_enabled,
        "selected_ensemble_method": ensemble.get("selected_method"),
        "selection_metric": optimize_for,
    }
    final_holdout = evaluate_final_holdout(holdout_policy_input_rows, selected_policy)
    selected_rows = final_holdout.get("scored_rows", [])
    selected_path = root / "selected_policy_holdout_rows.jsonl"
    _write_jsonl(selected_path, selected_rows)

    evidence = materialize_engine_evidence_from_training_run(
        run_root=str(root),
        evidence_root=str(root / "evidence"),
    )
    if selected_path.exists():
        (root / "evidence").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(selected_path, root / "evidence" / "selected_policy_holdout_rows.jsonl")
    engine = run_engine_universe_with_generated_evidence(
        evidence_root=str(root / "evidence"),
        output_root=str(root / "engine_sweep"),
    )

    groups = final_holdout.get("accuracy_evaluation", {}).get("groups", {}) if isinstance(final_holdout.get("accuracy_evaluation"), dict) else {}
    result = {
        "pipeline_status": "completed_with_accuracy_maximization" if selected_rows else "completed_no_scored_holdout_rows",
        "output_root": str(root),
        "max_workers": max_workers,
        "max_models": max_models,
        "max_runtime_minutes": max_runtime_minutes,
        "optimize_for": optimize_for,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "plan": plan,
        "dataset": dataset_public,
        "training": training,
        "raw_validation_metrics": _metric_summary(train_validation_rows),
        "validation_policy_metrics": _metric_summary(train_validation_policy_rows),
        "signal_sanity_audit": signal_audit,
        "baseline_sanity_audit": baseline_audit,
        "purged_walk_forward": walk_forward,
        "flip_rescue_applied": flip_enabled,
        "selective_prediction": confidence,
        "diagnostic_ensemble": ensemble,
        "champion_selection": champion_selection,
        "selected_policy": selected_policy,
        "selected_policy_holdout_output": str(selected_path),
        "final_holdout": _public_result(final_holdout),
        "final_holdout_metrics": {
            "global_accuracy": final_holdout.get("global_accuracy"),
            "global_balanced_accuracy": final_holdout.get("global_balanced_accuracy"),
            "mcc": final_holdout.get("mcc"),
            "wilson_accuracy_interval": final_holdout.get("wilson_accuracy_interval"),
            "coverage": final_holdout.get("coverage"),
            "random_baseline": (final_holdout.get("baseline_comparison") or {}).get("random_50_50_baseline_accuracy"),
            "majority_baseline": (final_holdout.get("baseline_comparison") or {}).get("majority_class_baseline_accuracy"),
            "previous_direction_baseline": (final_holdout.get("baseline_comparison") or {}).get("previous_direction_baseline_accuracy"),
            "beats_random": final_holdout.get("beats_random"),
            "beats_majority": final_holdout.get("beats_majority"),
            "beats_previous_direction": final_holdout.get("beats_previous_direction"),
        },
        "best_horizon": _best_group(final_holdout.get("by_horizon") or {}),
        "best_ticker": _best_group(final_holdout.get("by_ticker") or {}),
        "best_ticker_horizon": _best_group((groups or {}).get("by_ticker_horizon") or {}),
        "evidence_materialization": evidence,
        "engine_universe": engine,
        "broad_superiority_claim_allowed": bool(
            final_holdout.get("beats_random")
            and final_holdout.get("beats_majority")
            and final_holdout.get("beats_previous_direction")
            and not (((baseline_audit.get("previous_direction_baseline") or {}).get("leakage_warning")))
        ),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "accuracy_maximization_summary.json", _public_result(result))
    return result


def render_accuracy_maximization_report(result: dict) -> str:
    """Render compact accuracy maximization results."""

    training = result.get("training") or {}
    holdout = result.get("final_holdout_metrics") or {}
    selective = result.get("selective_prediction") or {}
    selected = selective.get("selected_metrics") or {}
    ensemble = result.get("diagnostic_ensemble") or {}
    engine = result.get("engine_universe") or {}
    lines = [
        "# Accuracy Maximization Orchestrator",
        "",
        f"Pipeline status: {result.get('pipeline_status')}",
        f"Output root: {result.get('output_root')}",
        f"Elapsed seconds: {result.get('elapsed_seconds')}",
        f"Model groups attempted: {training.get('attempted_model_specs')}",
        f"Model groups trained: {training.get('trained_model_specs')}",
        f"Model groups tuned: {training.get('tuned_model_specs')}",
        f"Flip rescue applied: {result.get('flip_rescue_applied')}",
        "",
        "Final holdout:",
        f"- accuracy: {holdout.get('global_accuracy')}",
        f"- balanced accuracy: {holdout.get('global_balanced_accuracy')}",
        f"- MCC: {holdout.get('mcc')}",
        f"- Wilson interval: {holdout.get('wilson_accuracy_interval')}",
        f"- coverage: {holdout.get('coverage')}",
        f"- random baseline: {holdout.get('random_baseline')}",
        f"- majority baseline: {holdout.get('majority_baseline')}",
        f"- previous-direction baseline: {holdout.get('previous_direction_baseline')}",
        f"- beats random: {holdout.get('beats_random')}",
        f"- beats majority: {holdout.get('beats_majority')}",
        f"- beats previous direction: {holdout.get('beats_previous_direction')}",
        "",
        "Selective prediction:",
        f"- selected threshold: {selective.get('selected_threshold')}",
        f"- selected coverage: {selected.get('coverage')}",
        f"- selected balanced accuracy: {selected.get('balanced_accuracy')}",
        "",
        "Ensemble:",
        f"- selected method: {ensemble.get('selected_method')}",
        f"- selected metrics: {ensemble.get('selected_metrics')}",
        "",
        "Generated engine universe:",
        f"- completed specs: {engine.get('completed_count')}",
        f"- skipped specs: {engine.get('skipped_count')}",
        f"- failed specs: {engine.get('failed_count')}",
        "",
        f"Broad superiority claim allowed: {result.get('broad_superiority_claim_allowed')}",
        "",
        "Boundary:",
        "Final holdout metrics are local research diagnostics with explicit baselines and coverage.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded local accuracy maximization.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--max-models", type=int, default=None)
    parser.add_argument("--max-runtime-minutes", type=int, default=60)
    parser.add_argument("--optimize-for", choices=("balanced_accuracy", "directional_accuracy", "mcc"), default="balanced_accuracy")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_accuracy_maximization_pipeline(
        output_root=args.output_root,
        max_workers=args.max_workers,
        max_models=args.max_models,
        max_runtime_minutes=args.max_runtime_minutes,
        optimize_for=args.optimize_for,
    )
    public_result = _public_result(result)
    if args.format == "report":
        print(render_accuracy_maximization_report(public_result), end="")
    else:
        print(json.dumps(public_result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
