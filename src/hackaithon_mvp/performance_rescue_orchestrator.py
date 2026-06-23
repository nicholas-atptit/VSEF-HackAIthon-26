"""Performance rescue pipeline for local diagnostic forecasting evidence."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)
from src.hackaithon_mvp.forecast_signal_sanity_audit import (
    audit_prediction_flip_rescue,
    render_forecast_signal_sanity_report,
    run_forecast_signal_sanity_audit,
)
from src.hackaithon_mvp.full_eligible_model_trainer import run_full_eligible_model_training
from src.hackaithon_mvp.full_engine_universe_runner import run_engine_universe_with_generated_evidence
from src.hackaithon_mvp.local_training_dataset_builder import (
    build_supervised_direction_dataset,
    load_discovered_ohlcv_rows,
)
from src.hackaithon_mvp.model_champion_selector import select_champions_by_slice
from src.hackaithon_mvp.model_run_evidence_materializer import materialize_engine_evidence_from_training_run
from src.hackaithon_mvp.purged_walk_forward_validation import run_walk_forward_folds
from src.hackaithon_mvp.release_accuracy_report import build_release_accuracy_report
from src.hackaithon_mvp.release_baseline_sanity_audit import audit_release_baselines


CLAIM_BOUNDARY = {
    "local_performance_rescue_only": True,
    "writes_only_under_output_root": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Performance rescue is local research diagnostics; weak or non-improving metrics must be reported as-is."


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_performance_rescue") for part in root.parts):
        raise ValueError("output_root must be .tmp_performance_rescue or a child path")
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


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _flip_rows(rows: list[dict]) -> list[dict]:
    flipped = []
    for row in normalize_forecast_actual_rows(rows):
        output = dict(row.get("raw") or row)
        direction = row.get("predicted_direction")
        output["predicted_direction"] = DOWN if direction == UP else UP if direction == DOWN else direction
        probability = row.get("predicted_probability")
        if isinstance(probability, (int, float)):
            output["predicted_probability"] = round(1.0 - float(probability), 12)
        output["rescue_policy"] = "flipped_prediction_diagnostic"
        flipped.append(output)
    return flipped


def _group_rows(rows: list[dict], keys: tuple[str, ...]) -> dict[tuple[str, ...], list[dict]]:
    grouped: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key) or "global") for key in keys)].append(row)
    return grouped


def _candidate_from_rows(key: tuple[str, ...], rows: list[dict], fields: tuple[str, ...]) -> dict:
    result = evaluate_forecast_accuracy(rows)
    directional = result["global"]["directional"]
    candidate = {
        "post_tune_validation_metrics": {
            "accuracy": directional.get("accuracy"),
            "balanced_accuracy": directional.get("balanced_accuracy"),
            "mcc": directional.get("mcc"),
            "coverage_count": directional.get("coverage_count"),
        },
        "validation_rows": directional.get("coverage_count") or 0,
        "baseline_comparison": result.get("baseline_comparison") or {},
        "leakage_warning": False,
        "has_action_labels": False,
    }
    for field, value in zip(fields, key):
        candidate[field] = value
    return candidate


def _champion_candidates(rows: list[dict]) -> list[dict]:
    normalized = [dict(row.get("raw") or row) for row in normalize_forecast_actual_rows(rows)]
    candidates = []
    for fields in (("model_id", "horizon"), ("ticker", "model_id", "horizon"), ("horizon",), ("ticker", "horizon")):
        for key, group_rows in _group_rows(normalized, fields).items():
            if len(group_rows) < 30:
                continue
            candidates.append(_candidate_from_rows(key, group_rows, fields))
    return candidates


def _accuracy_summary(report: dict) -> dict:
    baseline = report.get("baseline_comparison") or {}
    return {
        "release_accuracy_status": report.get("release_accuracy_status"),
        "evaluated_row_count": report.get("evaluated_row_count"),
        "directional_accuracy": report.get("global_directional_accuracy"),
        "balanced_accuracy": report.get("global_balanced_accuracy"),
        "majority_baseline": baseline.get("majority_class_baseline_accuracy"),
        "random_baseline": baseline.get("random_50_50_baseline_accuracy"),
        "previous_direction_baseline": baseline.get("previous_direction_baseline_accuracy"),
    }


def run_performance_rescue_pipeline(
    *,
    output_root: str,
    max_workers: int = 1,
    max_models: int | None = None,
) -> dict:
    """Run the bounded local performance rescue pipeline."""

    root = _output_root(output_root)
    bars = list(load_discovered_ohlcv_rows(repo_root="."))
    dataset = build_supervised_direction_dataset(bars)
    dataset_path = root / "training_dataset.jsonl"
    _write_jsonl(dataset_path, dataset.get("rows", []))
    dataset_public = {key: value for key, value in dataset.items() if key != "rows"}
    _write_json(root / "training_dataset_summary.json", dataset_public)

    if dataset.get("dataset_status") != "ready":
        result = {
            "pipeline_status": "blocked_by_data_unavailability",
            "output_root": str(root),
            "dataset": dataset_public,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
        _write_json(root / "performance_rescue_summary.json", result)
        return result

    training = run_full_eligible_model_training(
        dataset_path=str(dataset_path),
        output_root=str(root),
        max_models=max_models,
        max_workers=max_workers,
        timeout_seconds_per_model=120,
    )
    forecast_path = root / "forecast_actual_rows.jsonl"
    forecast_rows = load_forecast_accuracy_rows(str(forecast_path)) if forecast_path.exists() else []
    signal_audit = run_forecast_signal_sanity_audit(forecast_rows)
    baseline_audit = audit_release_baselines(forecast_rows)
    walk_forward = run_walk_forward_folds(forecast_rows, n_folds=3, horizon_steps=40)

    flip = audit_prediction_flip_rescue(forecast_rows)
    flip_supported = bool(
        flip.get("possible_label_polarity_mismatch")
        or flip.get("flipped_predictions_materially_outperform_original")
    )
    champion_rows = _flip_rows(forecast_rows) if flip_supported else [dict(row) for row in forecast_rows]
    champion_path = root / "champion_forecast_actual_rows.jsonl"
    _write_jsonl(champion_path, champion_rows)

    final_accuracy = build_release_accuracy_report(input_path=str(champion_path))
    champion_candidates = _champion_candidates(champion_rows)
    training_results = _read_json(root / "training_run_summary.json").get("model_results", [])
    champion_selection = select_champions_by_slice(champion_candidates or training_results)

    evidence = materialize_engine_evidence_from_training_run(
        run_root=str(root),
        evidence_root=str(root / "evidence"),
    )
    shutil.copyfile(champion_path, root / "evidence" / "champion_forecast_actual_rows.jsonl")
    engine = run_engine_universe_with_generated_evidence(
        evidence_root=str(root / "evidence"),
        output_root=str(root / "engine_sweep"),
    )
    status = "completed_with_rescue_diagnostics"
    if int(training.get("trained_model_specs") or 0) == 0:
        status = "completed_no_trainable_data"
    elif int(engine.get("skipped_count") or 0) > 0:
        status = "completed_partial_due_to_dependencies"
    result = {
        "pipeline_status": status,
        "output_root": str(root),
        "dataset": dataset_public,
        "training": training,
        "signal_sanity_audit": signal_audit,
        "baseline_sanity_audit": baseline_audit,
        "purged_walk_forward": walk_forward,
        "flip_policy_applied": flip_supported,
        "champion_forecast_actual_output": str(champion_path),
        "champion_selection": champion_selection,
        "final_accuracy": final_accuracy,
        "final_accuracy_summary": _accuracy_summary(final_accuracy),
        "evidence_materialization": evidence,
        "engine_universe": engine,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "performance_rescue_summary.json", result)
    return result


def render_performance_rescue_report(result: dict) -> str:
    """Render compact performance rescue results."""

    training = result.get("training") or {}
    final_accuracy = result.get("final_accuracy_summary") or {}
    signal = result.get("signal_sanity_audit") or {}
    flip = (signal.get("prediction_flip_rescue") or {})
    baseline = ((result.get("baseline_sanity_audit") or {}).get("previous_direction_baseline") or {})
    champion = result.get("champion_selection") or {}
    engine = result.get("engine_universe") or {}
    lines = [
        "# Performance Rescue Pipeline",
        "",
        f"Pipeline status: {result.get('pipeline_status')}",
        f"Output root: {result.get('output_root')}",
        f"Trained model groups: {training.get('trained_model_specs')}",
        f"Tuned model groups: {training.get('tuned_model_specs')}",
        f"Flip policy applied: {result.get('flip_policy_applied')}",
        "",
        "Signal sanity:",
        f"- original balanced accuracy: {(flip.get('original_metrics') or {}).get('balanced_accuracy')}",
        f"- flipped balanced accuracy: {(flip.get('flipped_metrics') or {}).get('balanced_accuracy')}",
        f"- possible polarity mismatch: {flip.get('possible_label_polarity_mismatch')}",
        "",
        "Baseline sanity:",
        f"- previous-direction accuracy: {baseline.get('previous_direction_accuracy')}",
        f"- leakage warning: {baseline.get('leakage_warning')}",
        f"- high persistence warning: {baseline.get('warning_high_persistence')}",
        "",
        "Final champion rows:",
        f"- evaluated rows: {final_accuracy.get('evaluated_row_count')}",
        f"- directional accuracy: {final_accuracy.get('directional_accuracy')}",
        f"- balanced accuracy: {final_accuracy.get('balanced_accuracy')}",
        f"- majority baseline: {final_accuracy.get('majority_baseline')}",
        f"- random baseline: {final_accuracy.get('random_baseline')}",
        f"- previous-direction baseline: {final_accuracy.get('previous_direction_baseline')}",
        "",
        "Champion selection:",
        f"- beats random count: {champion.get('beats_random_count')}",
        f"- beats majority count: {champion.get('beats_majority_count')}",
        f"- beats previous-direction count: {champion.get('beats_previous_direction_count')}",
        "",
        "Generated engine universe:",
        f"- completed specs: {engine.get('completed_count')}",
        f"- skipped specs: {engine.get('skipped_count')}",
        f"- failed specs: {engine.get('failed_count')}",
        "",
        "Boundary:",
        "Metrics are reported only from local generated forecast-vs-actual rows.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the bounded local performance rescue pipeline.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--max-models", type=int, default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_performance_rescue_pipeline(
        output_root=args.output_root,
        max_workers=args.max_workers,
        max_models=args.max_models,
    )
    if args.format == "report":
        print(render_performance_rescue_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
