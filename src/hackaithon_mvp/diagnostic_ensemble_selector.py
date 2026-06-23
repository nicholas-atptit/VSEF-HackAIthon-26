"""Build and evaluate simple local diagnostic ensembles."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


MIN_GROUP_MODELS = 2
CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_update": True,
    "ensemble_selection_requires_validation_only": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Diagnostic ensemble selector builds fixed validation policies; final scoring must use untouched holdout rows."


def _row_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("ticker") or "unspecified"),
        str(row.get("horizon") or "unspecified"),
        str(row.get("forecast_timestamp") or row.get("source_index") or "unspecified"),
        str((row.get("raw") or {}).get("target") or row.get("target") or "absolute_direction"),
    )


def _base_row(row: dict, *, method: str, predicted_direction: str, probability: float | None) -> dict:
    raw = row.get("raw") or row
    output = {
        "ticker": row.get("ticker"),
        "model_id": f"diagnostic_ensemble::{method}",
        "model_family": "diagnostic_ensemble",
        "horizon": row.get("horizon"),
        "forecast_timestamp": row.get("forecast_timestamp"),
        "target": raw.get("target"),
        "predicted_direction": predicted_direction,
        "actual_direction": row.get("actual_direction"),
        "predicted_probability": probability,
        "actual_return": row.get("actual_return"),
        "ensemble_method": method,
    }
    return output


def _model_scores(rows: tuple[dict, ...], group_fields: tuple[str, ...] = ()) -> dict[tuple[str, ...], dict[str, float]]:
    grouped: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    for row in rows:
        group = tuple(str(row.get(field) or "global") for field in group_fields)
        grouped[group].append(row)
    output: dict[tuple[str, ...], dict[str, float]] = {}
    for group, group_rows in grouped.items():
        by_model: dict[str, list[dict]] = defaultdict(list)
        for row in group_rows:
            by_model[str(row.get("model_id") or "unspecified")].append(dict(row.get("raw") or row))
        scores = {}
        for model_id, model_rows in by_model.items():
            metric = evaluate_forecast_accuracy(model_rows)["global"]["directional"]
            score = metric.get("balanced_accuracy")
            scores[model_id] = float(score) if isinstance(score, (int, float)) else 0.0
        output[group] = scores
    return output


def _best_model(scores: dict[str, float]) -> str | None:
    if not scores:
        return None
    return sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]


def _probability(row: dict) -> float | None:
    value = row.get("predicted_probability")
    if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0:
        return float(value)
    direction = row.get("predicted_direction")
    if direction == UP:
        return 1.0
    if direction == DOWN:
        return 0.0
    return None


def _direction_from_probability(value: float | None) -> str | None:
    if value is None:
        return None
    return UP if value >= 0.5 else DOWN


def _apply_champion(group_rows: list[dict], champion_model: str | None, method: str) -> dict | None:
    if champion_model is None:
        return None
    for row in group_rows:
        if str(row.get("model_id")) == champion_model:
            probability = _probability(row)
            direction = row.get("predicted_direction") if row.get("predicted_direction") in {UP, DOWN} else _direction_from_probability(probability)
            if direction in {UP, DOWN}:
                return _base_row(row, method=method, predicted_direction=direction, probability=probability)
    return None


def _ensemble_rows(rows: tuple[dict, ...], method: str) -> list[dict]:
    grouped: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[_row_key(row)].append(row)
    global_scores = _model_scores(rows).get((), {})
    ticker_scores = _model_scores(rows, ("ticker",))
    horizon_scores = _model_scores(rows, ("horizon",))
    ticker_horizon_scores = _model_scores(rows, ("ticker", "horizon"))
    output = []
    for _, group_rows in grouped.items():
        if len({row.get("model_id") for row in group_rows}) < MIN_GROUP_MODELS:
            continue
        first = group_rows[0]
        if method == "majority_vote":
            counts = Counter(row.get("predicted_direction") for row in group_rows if row.get("predicted_direction") in {UP, DOWN})
            if not counts:
                continue
            direction = UP if counts.get(UP, 0) >= counts.get(DOWN, 0) else DOWN
            output.append(_base_row(first, method=method, predicted_direction=direction, probability=None))
        elif method == "probability_average":
            probabilities = [_probability(row) for row in group_rows]
            usable = [value for value in probabilities if value is not None]
            if not usable:
                continue
            probability = sum(usable) / len(usable)
            output.append(_base_row(first, method=method, predicted_direction=_direction_from_probability(probability), probability=round(probability, 6)))
        elif method == "weighted_probability_average":
            weighted_sum = 0.0
            weight_total = 0.0
            for row in group_rows:
                probability = _probability(row)
                if probability is None:
                    continue
                weight = max(global_scores.get(str(row.get("model_id")), 0.0), 0.01)
                weighted_sum += probability * weight
                weight_total += weight
            if weight_total == 0:
                continue
            probability = weighted_sum / weight_total
            output.append(_base_row(first, method=method, predicted_direction=_direction_from_probability(probability), probability=round(probability, 6)))
        elif method == "per_ticker_champion":
            ticker = str(first.get("ticker") or "global")
            row = _apply_champion(group_rows, _best_model(ticker_scores.get((ticker,), {})), method)
            if row:
                output.append(row)
        elif method == "per_horizon_champion":
            horizon = str(first.get("horizon") or "global")
            row = _apply_champion(group_rows, _best_model(horizon_scores.get((horizon,), {})), method)
            if row:
                output.append(row)
        elif method == "per_ticker_horizon_champion":
            ticker = str(first.get("ticker") or "global")
            horizon = str(first.get("horizon") or "global")
            row = _apply_champion(group_rows, _best_model(ticker_horizon_scores.get((ticker, horizon), {})), method)
            if row:
                output.append(row)
        elif method == "confidence_gated_champion_ensemble":
            ticker = str(first.get("ticker") or "global")
            horizon = str(first.get("horizon") or "global")
            row = _apply_champion(group_rows, _best_model(ticker_horizon_scores.get((ticker, horizon), {})), method)
            if row is None:
                continue
            probability = row.get("predicted_probability")
            confidence = max(float(probability), 1.0 - float(probability)) if isinstance(probability, (int, float)) else 0.0
            if confidence >= 0.55:
                row["diagnostic_retention_status"] = "diagnostic_prediction_retained"
                output.append(row)
    return output


def build_simple_ensembles(candidate_predictions: list[dict]) -> dict:
    """Build simple ensemble rows from local candidate predictions."""

    normalized = normalize_forecast_actual_rows(candidate_predictions)
    methods = (
        "majority_vote",
        "probability_average",
        "weighted_probability_average",
        "per_ticker_champion",
        "per_horizon_champion",
        "per_ticker_horizon_champion",
        "confidence_gated_champion_ensemble",
    )
    rows_by_method = {method: _ensemble_rows(normalized, method) for method in methods}
    return {
        "ensemble_status": "completed" if any(rows_by_method.values()) else "not_ready_insufficient_candidate_overlap",
        "input_rows": len(candidate_predictions),
        "normalized_rows": len(normalized),
        "methods": list(methods),
        "ensemble_rows_by_method": rows_by_method,
        "row_counts_by_method": {method: len(rows) for method, rows in rows_by_method.items()},
        "selection_boundary": "Learn method choice only on validation rows, then score fixed method on holdout rows.",
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def evaluate_ensemble_candidates(rows: list[dict]) -> dict:
    """Evaluate simple ensemble candidates over supplied validation rows."""

    ensembles = build_simple_ensembles(rows)
    evaluations = {}
    for method, method_rows in ensembles.get("ensemble_rows_by_method", {}).items():
        result = evaluate_forecast_accuracy(method_rows)
        directional = result["global"]["directional"]
        evaluations[method] = {
            "row_count": len(method_rows),
            "accuracy": directional.get("accuracy"),
            "balanced_accuracy": directional.get("balanced_accuracy"),
            "mcc": directional.get("mcc"),
            "baseline_comparison": result.get("baseline_comparison"),
        }
    selectable = [
        {"method": method, **metric}
        for method, metric in evaluations.items()
        if isinstance(metric.get("balanced_accuracy"), (int, float))
    ]
    selectable.sort(
        key=lambda item: (
            float(item.get("balanced_accuracy") or -999.0),
            float(item.get("mcc") or -999.0),
            int(item.get("row_count") or 0),
        ),
        reverse=True,
    )
    return {
        "ensemble_evaluation_status": "completed" if selectable else ensembles.get("ensemble_status"),
        "selected_method": selectable[0]["method"] if selectable else None,
        "selected_metrics": selectable[0] if selectable else None,
        "evaluations": evaluations,
        "ensembles": {key: value for key, value in ensembles.items() if key != "ensemble_rows_by_method"},
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_diagnostic_ensemble_report(result: dict) -> str:
    """Render compact diagnostic ensemble results."""

    selected = result.get("selected_metrics") or {}
    lines = [
        "# Diagnostic Ensemble Selector",
        "",
        f"Evaluation status: {result.get('ensemble_evaluation_status')}",
        f"Selected method: {result.get('selected_method')}",
        f"Selected rows: {selected.get('row_count')}",
        f"Selected accuracy: {selected.get('accuracy')}",
        f"Selected balanced accuracy: {selected.get('balanced_accuracy')}",
        f"Selected MCC: {selected.get('mcc')}",
        "",
        "Methods:",
    ]
    for method, metrics in (result.get("evaluations") or {}).items():
        lines.append(
            f"- {method}: rows={metrics.get('row_count')}, accuracy={metrics.get('accuracy')}, "
            f"balanced_accuracy={metrics.get('balanced_accuracy')}, mcc={metrics.get('mcc')}"
        )
    if not result.get("evaluations"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "Ensemble method choice must be fixed before final holdout scoring.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate simple local diagnostic ensembles.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_forecast_accuracy_rows(args.input)
    result = evaluate_ensemble_candidates(rows)
    if args.format == "report":
        print(render_diagnostic_ensemble_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
