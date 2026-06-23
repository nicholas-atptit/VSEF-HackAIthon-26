"""Orchestrate a clean local forecast-edge pipeline with strict gates."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.clean_forecast_target_builder import build_clean_direction_targets
from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy
from src.hackaithon_mvp.forecast_data_expansion import run_optional_data_expansion
from src.hackaithon_mvp.forecast_edge_feature_builder import build_forecast_edge_features
from src.hackaithon_mvp.forecast_edge_model_trainer import train_forecast_edge_models
from src.hackaithon_mvp.forecast_edge_planner import build_forecast_edge_plan
from src.hackaithon_mvp.forecast_edge_selector import select_forecast_edge_slices
from src.hackaithon_mvp.full_engine_universe_runner import run_engine_universe_with_generated_evidence
from src.hackaithon_mvp.local_training_dataset_builder import load_discovered_ohlcv_rows


STATUS_FOUND = "forecast_edge_found"
STATUS_FOUND_LOW_COVERAGE = "forecast_edge_found_low_coverage"
STATUS_NOT_FOUND = "forecast_edge_not_found"
STATUS_BLOCKED_DATA = "blocked_by_data_quality"
STATUS_BLOCKED_INSUFFICIENT = "blocked_by_insufficient_data"
CLAIM_BOUNDARY = {
    "local_pipeline_only": True,
    "writes_only_under_tmp_forecast_edge": True,
    "no_live_data": True,
    "provider_fetch_disabled_by_default": True,
    "coverage_disclosed": True,
    "strict_gates_required": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast-edge pipeline reports selective local holdout diagnostics and abstains when gates fail."


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_forecast_edge") for part in root.parts):
        raise ValueError("output_root must be .tmp_forecast_edge or a child path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _public(payload: Any) -> Any:
    if isinstance(payload, dict):
        output = {}
        for key, value in payload.items():
            if key in {"rows", "retained_forecast_rows", "holdout_forecast_rows", "accuracy_evaluation"}:
                if isinstance(value, list):
                    output[f"{key}_count"] = len(value)
                continue
            output[key] = _public(value)
        return output
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            return [_public(item) for item in payload[:100]]
        return payload
    return payload


def _merge_targets_features(target_rows: list[dict], feature_rows: list[dict]) -> list[dict]:
    feature_by_key = {(str(row.get("ticker")), str(row.get("timestamp"))): row for row in feature_rows}
    merged = []
    for row in target_rows:
        key = (str(row.get("ticker")), str(row.get("timestamp") or row.get("forecast_timestamp")))
        features = feature_by_key.get(key, {})
        output = dict(row)
        for column, value in features.items():
            if str(column).startswith("feature_"):
                output[column] = value
        merged.append(output)
    return merged


def _materialize_edge_evidence(root: Path, retained_rows: list[dict], selection: dict) -> dict:
    evidence_root = root / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_jsonl(evidence_root / "forecast_actual_rows.jsonl", retained_rows)
    _write_json(evidence_root / "accuracy_summary.json", evaluate_forecast_accuracy(retained_rows))
    _write_json(evidence_root / "static_evidence.json", [])
    _write_jsonl(evidence_root / "dependency_results.jsonl", [])
    _write_json(evidence_root / "selection_summary.json", _public(selection))
    return {
        "materialization_status": "completed" if retained_rows else "no_retained_rows",
        "evidence_root": str(evidence_root),
        "retained_row_count": len(retained_rows),
        "outputs": {
            "forecast_actual_rows": str(evidence_root / "forecast_actual_rows.jsonl"),
            "accuracy_summary": str(evidence_root / "accuracy_summary.json"),
            "selection_summary": str(evidence_root / "selection_summary.json"),
        },
    }


def _run_engine_universe(root: Path, evidence_root: Path) -> dict:
    try:
        return run_engine_universe_with_generated_evidence(
            evidence_root=str(evidence_root),
            output_root=str(root / "engine_sweep"),
        )
    except ValueError as exc:
        return {
            "engine_universe_run_status": "skipped_after_retained_evidence",
            "completed_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "skip_reason": str(exc),
        }


def _status(selection: dict, *, target_rows: int, clean_training_rows: int) -> str:
    if target_rows == 0 or clean_training_rows == 0:
        return STATUS_BLOCKED_INSUFFICIENT
    if not selection.get("allowed_slice_count"):
        return STATUS_NOT_FOUND
    coverage = float(selection.get("retained_coverage") or 0.0)
    if coverage < 0.10:
        return STATUS_FOUND_LOW_COVERAGE
    return STATUS_FOUND


def run_forecast_edge_pipeline(
    *,
    output_root: str,
    max_models: int = 300,
    max_workers: int = 1,
    min_slice_rows: int = 300,
) -> dict:
    """Run the local clean forecast-edge pipeline."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    started = time.monotonic()
    root = _output_root(output_root)
    plan = build_forecast_edge_plan(repo_root=".")
    _write_json(root / "forecast_edge_plan.json", _public(plan))

    data_expansion = run_optional_data_expansion(output_root=str(root))
    _write_json(root / "data_expansion.json", _public(data_expansion))

    bars = list(load_discovered_ohlcv_rows(repo_root="."))
    _write_jsonl(root / "local_bars_sample.jsonl", bars[:100])
    targets = build_clean_direction_targets(bars, horizons=(1, 5, 10, 20), non_overlapping=True)
    target_rows = list(targets.get("rows") or [])
    _write_jsonl(root / "clean_target_rows.jsonl", target_rows)
    _write_json(root / "clean_target_summary.json", _public(targets))

    features = build_forecast_edge_features(bars)
    feature_rows = list(features.get("rows") or [])
    _write_jsonl(root / "feature_rows.jsonl", feature_rows)
    _write_json(root / "feature_summary.json", _public(features))

    training_rows = _merge_targets_features(target_rows, feature_rows)
    _write_jsonl(root / "edge_training_rows.jsonl", training_rows)
    training = train_forecast_edge_models(
        training_rows,
        horizons=(1, 5, 10, 20),
        max_models=max_models,
        max_workers=max_workers,
        min_slice_rows=min_slice_rows,
    )
    _write_json(root / "forecast_edge_training_summary.json", _public(training))

    selection = select_forecast_edge_slices(list(training.get("model_results") or []))
    retained_rows = list(selection.get("retained_forecast_rows") or [])
    _write_jsonl(root / "retained_forecast_rows.jsonl", retained_rows)
    _write_json(root / "forecast_edge_selection_summary.json", _public(selection))

    evidence = _materialize_edge_evidence(root, retained_rows, selection)
    engine = _run_engine_universe(root, Path(evidence["evidence_root"]))
    _write_json(root / "engine_universe_summary.json", _public(engine))

    status = _status(selection, target_rows=len(target_rows), clean_training_rows=int(training.get("clean_training_rows") or 0))
    result = {
        "forecast_edge_status": status,
        "output_root": str(root),
        "data_expansion_used": data_expansion.get("data_expansion_status") not in {"disabled_by_default", "missing_required_config", "provider_not_configured"},
        "data_expansion": data_expansion,
        "plan": plan,
        "clean_targets": {key: value for key, value in targets.items() if key != "rows"},
        "features": {key: value for key, value in features.items() if key != "rows"},
        "training": training,
        "selection": selection,
        "evidence": evidence,
        "engine_universe": engine,
        "clean_target_rows": len(target_rows),
        "feature_blocks_generated": features.get("feature_blocks") or [],
        "feature_columns_generated": len(features.get("feature_columns") or []),
        "model_groups_attempted": training.get("attempted_model_specs"),
        "model_groups_trained": training.get("trained_model_specs"),
        "model_groups_tuned": training.get("tuned_model_specs"),
        "allowed_forecast_slices": selection.get("allowed_slice_count"),
        "rejected_forecast_slices": selection.get("rejected_slice_count"),
        "retained_coverage": selection.get("retained_coverage"),
        "retained_holdout_accuracy": selection.get("retained_holdout_accuracy"),
        "retained_holdout_balanced_accuracy": selection.get("retained_holdout_balanced_accuracy"),
        "retained_holdout_mcc": selection.get("retained_holdout_mcc"),
        "retained_baselines": selection.get("retained_baselines"),
        "beats_random": selection.get("beats_random"),
        "beats_majority": selection.get("beats_majority"),
        "beats_previous_direction": selection.get("beats_previous_direction"),
        "best_horizon": selection.get("best_horizon"),
        "best_ticker": selection.get("best_ticker"),
        "best_ticker_horizon": selection.get("best_ticker_horizon"),
        "selective_forecast_claim_allowed": bool(selection.get("selective_forecast_claim_allowed")),
        "broad_performance_claim_allowed": bool(selection.get("broad_performance_claim_allowed")),
        "lower_confidence_exploratory": int(min_slice_rows) < 300,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "forecast_edge_summary.json", _public(result))
    return result


def render_forecast_edge_report(result: dict) -> str:
    """Render the final forecast-edge pipeline report."""

    baselines = result.get("retained_baselines") or {}
    lines = [
        "# Forecast Edge Orchestrator",
        "",
        f"Forecast edge status: {result.get('forecast_edge_status')}",
        f"Data expansion used: {result.get('data_expansion_used')}",
        f"Clean target rows: {result.get('clean_target_rows')}",
        f"Feature blocks generated: {result.get('feature_blocks_generated')}",
        f"Feature columns generated: {result.get('feature_columns_generated')}",
        f"Model groups attempted: {result.get('model_groups_attempted')}",
        f"Model groups trained: {result.get('model_groups_trained')}",
        f"Model groups tuned: {result.get('model_groups_tuned')}",
        f"Allowed forecast slices: {result.get('allowed_forecast_slices')}",
        f"Rejected forecast slices: {result.get('rejected_forecast_slices')}",
        f"Retained coverage: {result.get('retained_coverage')}",
        f"Retained holdout accuracy: {result.get('retained_holdout_accuracy')}",
        f"Retained holdout balanced accuracy: {result.get('retained_holdout_balanced_accuracy')}",
        f"Retained holdout MCC: {result.get('retained_holdout_mcc')}",
        "",
        "Retained baselines:",
        f"- random: {baselines.get('random')}",
        f"- majority: {baselines.get('majority')}",
        f"- previous direction: {baselines.get('previous_direction')}",
        "",
        "Baseline gates:",
        f"- beats random: {result.get('beats_random')}",
        f"- beats majority: {result.get('beats_majority')}",
        f"- beats previous direction: {result.get('beats_previous_direction')}",
        f"- selective claim allowed: {result.get('selective_forecast_claim_allowed')}",
        f"- broad claim allowed: {result.get('broad_performance_claim_allowed')}",
        "",
        "Engine universe:",
        f"- status: {(result.get('engine_universe') or {}).get('engine_universe_run_status')}",
        f"- completed: {(result.get('engine_universe') or {}).get('completed_count')}",
        f"- skipped: {(result.get('engine_universe') or {}).get('skipped_count')}",
        f"- failed: {(result.get('engine_universe') or {}).get('failed_count')}",
        "",
        "Boundary:",
    ]
    if result.get("lower_confidence_exploratory"):
        lines.append("This run used lower min-slice rows and is exploratory lower-confidence evidence.")
    if result.get("forecast_edge_status") in {STATUS_NOT_FOUND, STATUS_BLOCKED_DATA, STATUS_BLOCKED_INSUFFICIENT}:
        lines.append("No robust forecast edge was found on current local data under strict holdout gates.")
    lines.extend(
        [
            "Coverage is disclosed with every retained metric.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local forecast-edge pipeline.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-models", type=int, default=300)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--min-slice-rows", type=int, default=300)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_forecast_edge_pipeline(
        output_root=args.output_root,
        max_models=args.max_models,
        max_workers=args.max_workers,
        min_slice_rows=args.min_slice_rows,
    )
    if args.format == "report":
        print(render_forecast_edge_report(result), end="")
    else:
        print(json.dumps(_public(result), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
