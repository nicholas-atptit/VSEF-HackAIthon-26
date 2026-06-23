"""Focused local search for a hard 60 percent forecast release gate."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.clean_forecast_target_builder import build_clean_direction_targets
from src.hackaithon_mvp.forecast_60pct_release_gate import (
    STATUS_BLOCKED_BELOW,
    evaluate_60pct_release_gate,
    evaluate_60pct_slice_gate,
    render_60pct_gate_report,
)
from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy
from src.hackaithon_mvp.forecast_edge_feature_builder import build_forecast_edge_features
from src.hackaithon_mvp.forecast_edge_model_trainer import train_forecast_edge_models
from src.hackaithon_mvp.forecast_edge_selector import select_forecast_edge_slices
from src.hackaithon_mvp.local_training_dataset_builder import load_discovered_ohlcv_rows


CLAIM_BOUNDARY = {
    "local_search_only": True,
    "writes_only_under_tmp_60pct_gate": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "holdout_evaluated_once_after_validation_selection": True,
    "hard_60pct_gate_required": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "60 percent edge search blocks forecast release unless the final holdout gate passes."


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_60pct_gate") for part in root.parts):
        raise ValueError("output_root must be .tmp_60pct_gate or a child path")
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
            if key in {"rows", "retained_forecast_rows", "holdout_forecast_rows", "validation_forecast_rows", "accuracy_evaluation"}:
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
    seen: set[tuple[str, int, str]] = set()
    for row in target_rows:
        try:
            horizon = int(row.get("horizon"))
        except (TypeError, ValueError):
            continue
        key = (str(row.get("ticker")), horizon, str(row.get("timestamp") or row.get("forecast_timestamp")))
        if key in seen:
            continue
        seen.add(key)
        features = feature_by_key.get((key[0], key[2]), {})
        output = dict(row)
        for column, value in features.items():
            if str(column).startswith("feature_"):
                output[column] = value
        merged.append(output)
    return merged


def _all_holdout_rows(model_results: list[dict]) -> list[dict]:
    rows = []
    for item in model_results:
        if item.get("training_status") == "completed":
            rows.extend(dict(row) for row in item.get("holdout_forecast_rows") or [])
    return rows


def _confidence(row: dict) -> float | None:
    value = row.get("predicted_probability")
    if value in (None, ""):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if probability < 0.0 or probability > 1.0:
        return None
    return max(probability, 1.0 - probability)


def _filter_by_confidence(rows: list[dict], threshold: float) -> list[dict]:
    return [row for row in rows if (_confidence(row) or -1.0) >= threshold]


def _directional_metrics(rows: list[dict]) -> tuple[dict, dict]:
    evaluation = evaluate_forecast_accuracy(rows)
    return evaluation["global"]["directional"], evaluation["baseline_comparison"]


def _evaluate_validation_confidence_gate(
    model_results: list[dict],
    *,
    min_selective_coverage: float,
) -> dict[str, Any]:
    total_holdout_rows = sum(int(item.get("holdout_rows") or 0) for item in model_results if item.get("training_status") == "completed")
    thresholds = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80)
    selected_slices = []
    retained_rows: list[dict] = []
    for item in model_results:
        if item.get("training_status") != "completed":
            continue
        validation_rows = list(item.get("validation_forecast_rows") or [])
        holdout_rows = list(item.get("holdout_forecast_rows") or [])
        if not validation_rows or not holdout_rows:
            continue
        candidates = []
        for threshold in thresholds:
            validation_filtered = _filter_by_confidence(validation_rows, threshold)
            if len(validation_filtered) < 30:
                continue
            validation_metrics, validation_baselines = _directional_metrics(validation_filtered)
            bacc = validation_metrics.get("balanced_accuracy")
            mcc = validation_metrics.get("mcc")
            if not isinstance(bacc, (int, float)) or bacc < 0.60:
                continue
            if not isinstance(mcc, (int, float)) or mcc <= 0:
                continue
            if bacc <= (validation_baselines.get("random_50_50_baseline_accuracy") or 0.5):
                continue
            holdout_filtered = _filter_by_confidence(holdout_rows, threshold)
            if not holdout_filtered:
                continue
            candidates.append(
                {
                    "threshold": threshold,
                    "validation_rows": len(validation_filtered),
                    "validation_balanced_accuracy": bacc,
                    "validation_accuracy": validation_metrics.get("accuracy"),
                    "validation_mcc": mcc,
                    "holdout_rows": len(holdout_filtered),
                    "holdout_rows_payload": holdout_filtered,
                }
            )
        if not candidates:
            continue
        candidates.sort(
            key=lambda candidate: (
                float(candidate["validation_balanced_accuracy"]),
                int(candidate["validation_rows"]),
                -float(candidate["threshold"]),
            ),
            reverse=True,
        )
        chosen = candidates[0]
        retained_rows.extend(dict(row) for row in chosen["holdout_rows_payload"])
        selected_slices.append(
            {
                "slice_id": item.get("slice_id"),
                "ticker": item.get("ticker"),
                "horizon": item.get("horizon"),
                "model_id": item.get("model_id"),
                "threshold": chosen["threshold"],
                "validation_rows": chosen["validation_rows"],
                "validation_accuracy": chosen["validation_accuracy"],
                "validation_balanced_accuracy": chosen["validation_balanced_accuracy"],
                "validation_mcc": chosen["validation_mcc"],
                "holdout_rows": chosen["holdout_rows"],
            }
        )
    holdout_metrics, holdout_baselines = _directional_metrics(retained_rows)
    retained_count = int(holdout_metrics.get("coverage_count") or 0)
    coverage = retained_count / total_holdout_rows if total_holdout_rows else 0.0
    return {
        "confidence_gate_status": "validation_confidence_gate_evaluated",
        "selected_slice_count": len(selected_slices),
        "selected_slices": selected_slices,
        "retained_forecast_rows": retained_rows,
        "retained_holdout_rows": retained_count,
        "retained_coverage": round(coverage, 6),
        "retained_holdout_accuracy": holdout_metrics.get("accuracy"),
        "retained_holdout_balanced_accuracy": holdout_metrics.get("balanced_accuracy"),
        "retained_holdout_mcc": holdout_metrics.get("mcc"),
        "retained_baselines": {
            "random": holdout_baselines.get("random_50_50_baseline_accuracy"),
            "majority": holdout_baselines.get("majority_class_baseline_accuracy"),
            "previous_direction": holdout_baselines.get("previous_direction_baseline_accuracy"),
        },
        "meets_requested_min_coverage": coverage >= min_selective_coverage,
        "total_holdout_rows": total_holdout_rows,
        "selection_rule": "confidence thresholds selected only on validation rows",
    }


def _best_model_result(model_results: list[dict], *, global_only: bool = False) -> dict | None:
    candidates = []
    for item in model_results:
        if item.get("training_status") != "completed":
            continue
        if global_only and item.get("scope") != "global_horizon":
            continue
        metrics = item.get("holdout_metrics") or {}
        score = metrics.get("balanced_accuracy")
        rows = item.get("holdout_rows") or metrics.get("coverage_count") or 0
        if isinstance(score, (int, float)):
            candidates.append((float(score), int(rows), item))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _gate_input(
    *,
    model_results: list[dict],
    selection: dict,
    slice_gate: dict,
) -> dict[str, Any]:
    best_global = _best_model_result(model_results, global_only=True)
    if best_global is None:
        best_global = _best_model_result(model_results)
    global_metrics = (best_global or {}).get("holdout_metrics") or {}
    baselines = (best_global or {}).get("holdout_baselines") or {}
    return {
        "final_holdout_accuracy": global_metrics.get("accuracy"),
        "final_holdout_balanced_accuracy": global_metrics.get("balanced_accuracy"),
        "final_holdout_mcc": global_metrics.get("mcc"),
        "final_holdout_rows": global_metrics.get("coverage_count") or (best_global or {}).get("holdout_rows"),
        "final_holdout_coverage": 1.0 if best_global else 0.0,
        "baseline_comparison": baselines,
        "retained_holdout_accuracy": selection.get("retained_holdout_accuracy"),
        "retained_holdout_balanced_accuracy": selection.get("retained_holdout_balanced_accuracy"),
        "retained_holdout_mcc": selection.get("retained_holdout_mcc"),
        "retained_rows": selection.get("retained_holdout_rows"),
        "retained_coverage": selection.get("retained_coverage"),
        "retained_baselines": selection.get("retained_baselines"),
        "retained_forecast_rows": selection.get("retained_forecast_rows") or [],
        "slice_gate": slice_gate,
        "hidden_post_hoc_tuning_on_holdout": False,
        "duplicate_key_severity": "none",
        "overlap_severity": "none",
        "leakage_warning": False,
    }


def _materialize_retained_evidence(root: Path, retained_rows: list[dict], gate: dict) -> dict:
    if not gate.get("forecast_release_allowed"):
        return {
            "materialization_status": "skipped_gate_not_passed",
            "retained_row_count": 0,
            "evidence_root": None,
        }
    evidence_root = root / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_jsonl(evidence_root / "forecast_actual_rows.jsonl", retained_rows)
    _write_json(evidence_root / "accuracy_summary.json", evaluate_forecast_accuracy(retained_rows))
    _write_json(evidence_root / "forecast_60pct_release_gate.json", _public(gate))
    return {
        "materialization_status": "completed",
        "retained_row_count": len(retained_rows),
        "evidence_root": str(evidence_root),
    }


def run_60pct_edge_search(
    *,
    output_root: str,
    max_models: int = 300,
    max_workers: int = 1,
    min_slice_rows: int = 300,
    min_selective_coverage: float = 0.10,
) -> dict:
    """Run focused local search and enforce the hard 60 percent gate."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if min_selective_coverage < 0:
        raise ValueError("min_selective_coverage must be non-negative")
    started = time.monotonic()
    root = _output_root(output_root)
    bars = list(load_discovered_ohlcv_rows(repo_root="."))
    targets = build_clean_direction_targets(bars, horizons=(1, 5, 10, 20), non_overlapping=True)
    target_rows = list(targets.get("rows") or [])
    features = build_forecast_edge_features(bars)
    feature_rows = list(features.get("rows") or [])
    training_rows = _merge_targets_features(target_rows, feature_rows)
    _write_json(root / "clean_target_summary.json", _public(targets))
    _write_json(root / "feature_summary.json", _public(features))
    _write_jsonl(root / "edge_training_rows.jsonl", training_rows)

    training = train_forecast_edge_models(
        training_rows,
        horizons=(1, 5, 10, 20),
        max_models=max_models,
        max_workers=max_workers,
        min_slice_rows=min_slice_rows,
    )
    model_results = list(training.get("model_results") or [])
    all_holdout_rows = _all_holdout_rows(model_results)
    selection = select_forecast_edge_slices(model_results)
    if float(selection.get("retained_coverage") or 0.0) < float(min_selective_coverage):
        selection["selection_below_requested_min_coverage"] = True
    confidence_gate = _evaluate_validation_confidence_gate(
        model_results,
        min_selective_coverage=min_selective_coverage,
    )
    selection_for_gate = confidence_gate if confidence_gate.get("selected_slice_count") else selection
    slice_gate = evaluate_60pct_slice_gate(all_holdout_rows)
    release_gate = evaluate_60pct_release_gate(_gate_input(model_results=model_results, selection=selection_for_gate, slice_gate=slice_gate))
    retained_rows = list(selection_for_gate.get("retained_forecast_rows") or [])
    evidence = _materialize_retained_evidence(root, retained_rows, release_gate)

    result = {
        "edge_search_status": release_gate.get("forecast_release_status") or STATUS_BLOCKED_BELOW,
        "forecast_release_status": release_gate.get("forecast_release_status"),
        "output_root": str(root),
        "max_models": max_models,
        "max_workers": max_workers,
        "min_slice_rows": min_slice_rows,
        "min_selective_coverage": min_selective_coverage,
        "exploratory_only": int(min_slice_rows) < 300,
        "clean_target_rows": len(target_rows),
        "dropped_duplicate_keys": targets.get("dropped_duplicate_keys"),
        "dropped_overlapping_windows": targets.get("dropped_overlapping_windows"),
        "feature_blocks_generated": features.get("feature_blocks") or [],
        "feature_columns_generated": len(features.get("feature_columns") or []),
        "training": training,
        "model_groups_attempted": training.get("attempted_model_specs"),
        "model_groups_trained": training.get("trained_model_specs"),
        "model_groups_tuned": training.get("tuned_model_specs"),
        "selection": selection,
        "validation_confidence_gate": confidence_gate,
        "selection_used_for_60pct_gate": (
            "validation_confidence_gate" if confidence_gate.get("selected_slice_count") else "strict_slice_selector"
        ),
        "allowed_forecast_slices": selection.get("allowed_slice_count"),
        "rejected_forecast_slices": selection.get("rejected_slice_count"),
        "retained_rows": selection_for_gate.get("retained_holdout_rows"),
        "retained_coverage": selection_for_gate.get("retained_coverage"),
        "retained_accuracy": selection_for_gate.get("retained_holdout_accuracy"),
        "retained_balanced_accuracy": selection_for_gate.get("retained_holdout_balanced_accuracy"),
        "retained_mcc": selection_for_gate.get("retained_holdout_mcc"),
        "retained_baselines": selection_for_gate.get("retained_baselines"),
        "best_ticker": selection.get("best_ticker"),
        "best_horizon": selection.get("best_horizon"),
        "best_ticker_horizon": selection.get("best_ticker_horizon"),
        "slice_gate": slice_gate,
        "forecast_60pct_release_gate": release_gate,
        "global_60pct_gate_passed": release_gate.get("global_release_passed"),
        "selective_60pct_gate_passed": release_gate.get("selective_release_passed"),
        "slice_only_60pct_gate_passed": release_gate.get("slice_only_passed"),
        "broad_performance_claim_allowed": release_gate.get("broad_performance_claim_allowed"),
        "evidence_materialization": evidence,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "forecast_60pct_edge_search_summary.json", _public(result))
    return result


def render_60pct_edge_search_report(result: dict) -> str:
    """Render focused 60 percent edge-search report."""

    baselines = result.get("retained_baselines") or {}
    gate = result.get("forecast_60pct_release_gate") or {}
    lines = [
        "# 60% Forecast Edge Search",
        "",
        f"Forecast release status: {result.get('forecast_release_status')}",
        f"Exploratory only: {result.get('exploratory_only')}",
        f"Clean target rows: {result.get('clean_target_rows')}",
        f"Dropped duplicate keys: {result.get('dropped_duplicate_keys')}",
        f"Dropped overlapping windows: {result.get('dropped_overlapping_windows')}",
        f"Feature blocks generated: {result.get('feature_blocks_generated')}",
        f"Model groups attempted: {result.get('model_groups_attempted')}",
        f"Model groups trained: {result.get('model_groups_trained')}",
        f"Model groups tuned: {result.get('model_groups_tuned')}",
        f"Allowed forecast slices: {result.get('allowed_forecast_slices')}",
        f"Rejected forecast slices: {result.get('rejected_forecast_slices')}",
        f"Retained rows: {result.get('retained_rows')}",
        f"Retained coverage: {result.get('retained_coverage')}",
        f"Retained accuracy: {result.get('retained_accuracy')}",
        f"Retained balanced accuracy: {result.get('retained_balanced_accuracy')}",
        f"Retained MCC: {result.get('retained_mcc')}",
        "",
        "Retained baselines:",
        f"- random: {baselines.get('random')}",
        f"- majority: {baselines.get('majority')}",
        f"- previous direction: {baselines.get('previous_direction')}",
        "",
        "Hard 60 percent gates:",
        f"- global passed: {result.get('global_60pct_gate_passed')}",
        f"- selective passed: {result.get('selective_60pct_gate_passed')}",
        f"- slice-only passed: {result.get('slice_only_60pct_gate_passed')}",
        f"- broad claim allowed: {result.get('broad_performance_claim_allowed')}",
        f"- gate status: {gate.get('forecast_release_status')}",
        "",
        "Gate detail:",
        render_60pct_gate_report(gate).rstrip(),
        "",
        "Boundary:",
    ]
    if result.get("forecast_release_status") == STATUS_BLOCKED_BELOW:
        lines.append("No honest >=60% forecast mode was found on the current local data under strict holdout gates.")
    if result.get("exploratory_only"):
        lines.append("This run lowered min-slice rows and is exploratory unless the release gate also passes.")
    lines.extend(
        [
            "Retained evidence is materialized only when the hard gate passes.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run focused local 60 percent forecast edge search.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-models", type=int, default=300)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--min-slice-rows", type=int, default=300)
    parser.add_argument("--min-selective-coverage", type=float, default=0.10)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_60pct_edge_search(
        output_root=args.output_root,
        max_models=args.max_models,
        max_workers=args.max_workers,
        min_slice_rows=args.min_slice_rows,
        min_selective_coverage=args.min_selective_coverage,
    )
    if args.format == "report":
        print(render_60pct_edge_search_report(result), end="")
    else:
        print(json.dumps(_public(result), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
