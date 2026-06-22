"""Release-grade local forecast-vs-actual accuracy evaluator."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_actual_artifact_discovery import discover_forecast_actual_artifacts


UP = "up"
DOWN = "down"
FLAT = "flat"
BINARY_DIRECTIONS = {UP, DOWN}
TICKER_ALIASES = ("ticker", "symbol")
MODEL_ALIASES = ("model_id", "model_key", "engine_id", "model", "model_name")
FAMILY_ALIASES = ("model_family", "family")
HORIZON_ALIASES = ("horizon", "horizon_steps")
TIME_ALIASES = ("forecast_timestamp", "prediction_timestamp", "asof", "date", "datetime", "timestamp")
PREDICTED_DIRECTION_ALIASES = ("predicted_direction", "y_pred", "pred_label", "forecast_diagnostic")
ACTUAL_DIRECTION_ALIASES = ("actual_direction", "y_true", "actual_label", "actual_direction_label")
PREDICTED_RETURN_ALIASES = ("predicted_return", "forecast_return")
ACTUAL_RETURN_ALIASES = ("actual_return", "realized_return", "actual_future_return")
PROBABILITY_ALIASES = ("predicted_probability", "prob_up", "score", "y_score_or_probability")
CLAIM_BOUNDARY = {
    "local_forecast_actual_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_model_update": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local accuracy evaluation only; metrics require explicit forecast-vs-actual rows."


def _first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    lowered = {str(key).lower(): key for key in row}
    for alias in aliases:
        key = lowered.get(alias)
        if key is not None and row[key] not in (None, ""):
            return row[key]
    return None


def _safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _safe_probability(value: Any) -> float | None:
    number = _safe_float(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        return number
    return None


def _normalize_direction(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    mapping = {
        "up": UP,
        "positive": UP,
        "positive_bias": UP,
        "pos": UP,
        "1": UP,
        "+1": UP,
        "true": UP,
        "down": DOWN,
        "negative": DOWN,
        "negative_bias": DOWN,
        "neg": DOWN,
        "-1": DOWN,
        "false": DOWN,
        "flat": FLAT,
        "neutral": FLAT,
        "neutral_or_uncertain": FLAT,
        "insufficient_evidence": FLAT,
        "exploratory_only": FLAT,
        "0": DOWN,
    }
    return mapping.get(text)


def _direction_from_return(value: float | None) -> str | None:
    if value is None:
        return None
    if value > 0:
        return UP
    if value < 0:
        return DOWN
    return FLAT


def _direction_from_probability(value: float | None, *, threshold: float = 0.5) -> str | None:
    if value is None:
        return None
    return UP if value >= threshold else DOWN


def _normalize_horizon(value: Any) -> str:
    if value in (None, ""):
        return "unspecified"
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except (TypeError, ValueError):
        pass
    return str(value).strip() or "unspecified"


def _normalize_row(row: dict[str, Any], index: int) -> dict[str, Any] | None:
    predicted_return = _safe_float(_first_value(row, PREDICTED_RETURN_ALIASES))
    actual_return = _safe_float(_first_value(row, ACTUAL_RETURN_ALIASES))
    probability = _safe_probability(_first_value(row, PROBABILITY_ALIASES))
    predicted_direction = _normalize_direction(_first_value(row, PREDICTED_DIRECTION_ALIASES))
    actual_direction = _normalize_direction(_first_value(row, ACTUAL_DIRECTION_ALIASES))
    if predicted_direction is None:
        predicted_direction = _direction_from_return(predicted_return)
    if predicted_direction is None:
        predicted_direction = _direction_from_probability(probability)
    if actual_direction is None:
        actual_direction = _direction_from_return(actual_return)
    if predicted_direction is None and predicted_return is None and probability is None:
        return None
    if actual_direction is None and actual_return is None:
        return None
    ticker = str(_first_value(row, TICKER_ALIASES) or "unspecified").strip().upper() or "unspecified"
    model_id = str(_first_value(row, MODEL_ALIASES) or "unspecified").strip() or "unspecified"
    model_family = str(_first_value(row, FAMILY_ALIASES) or "unspecified").strip() or "unspecified"
    horizon = _normalize_horizon(_first_value(row, HORIZON_ALIASES))
    timestamp = str(_first_value(row, TIME_ALIASES) or f"row_index_{index}").strip()
    return {
        "ticker": ticker,
        "model_id": model_id,
        "model_family": model_family,
        "horizon": horizon,
        "forecast_timestamp": timestamp,
        "predicted_direction": predicted_direction,
        "actual_direction": actual_direction,
        "predicted_return": predicted_return,
        "actual_return": actual_return,
        "predicted_probability": probability,
        "source_index": index,
        "raw": dict(row),
    }


def normalize_forecast_actual_rows(rows: list[dict]) -> tuple[dict, ...]:
    """Normalize supported forecast-vs-actual row aliases into a stable schema."""

    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item = _normalize_row(row, index)
        if item is not None:
            normalized.append(item)
    return tuple(normalized)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return round(2 * precision * recall / (precision + recall), 6)


def _wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float | None]:
    if total <= 0:
        return {"lower": None, "upper": None}
    p_hat = successes / total
    denominator = 1 + z * z / total
    center = (p_hat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * total)) / total) / denominator
    return {"lower": round(max(0.0, center - margin), 6), "upper": round(min(1.0, center + margin), 6)}


def _binary_rows(rows: tuple[dict, ...]) -> list[dict]:
    return [
        row
        for row in rows
        if row.get("predicted_direction") in BINARY_DIRECTIONS and row.get("actual_direction") in BINARY_DIRECTIONS
    ]


def evaluate_directional_accuracy(rows: list[dict]) -> dict:
    """Evaluate binary directional accuracy from normalized or alias-heavy rows."""

    normalized = normalize_forecast_actual_rows(rows)
    eligible = _binary_rows(normalized)
    tp = sum(1 for row in eligible if row["actual_direction"] == UP and row["predicted_direction"] == UP)
    tn = sum(1 for row in eligible if row["actual_direction"] == DOWN and row["predicted_direction"] == DOWN)
    fp = sum(1 for row in eligible if row["actual_direction"] == DOWN and row["predicted_direction"] == UP)
    fn = sum(1 for row in eligible if row["actual_direction"] == UP and row["predicted_direction"] == DOWN)
    positive_actual = tp + fn
    negative_actual = tn + fp
    positive_predicted = tp + fp
    negative_predicted = tn + fn
    correct = tp + tn
    accuracy = _ratio(correct, len(eligible))
    recall_up = _ratio(tp, positive_actual)
    recall_down = _ratio(tn, negative_actual)
    precision_up = _ratio(tp, positive_predicted)
    precision_down = _ratio(tn, negative_predicted)
    balanced_accuracy = None
    if recall_up is not None and recall_down is not None:
        balanced_accuracy = round((recall_up + recall_down) / 2, 6)
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = None if denominator == 0 else round(((tp * tn) - (fp * fn)) / denominator, 6)
    return {
        "sample_count": len(normalized),
        "coverage_count": len(eligible),
        "positive_actual_count": positive_actual,
        "negative_actual_count": negative_actual,
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "precision_up": precision_up,
        "recall_up": recall_up,
        "f1_up": _f1(precision_up, recall_up),
        "precision_down": precision_down,
        "recall_down": recall_down,
        "f1_down": _f1(precision_down, recall_down),
        "confusion_matrix": {
            "actual_up": {"predicted_up": tp, "predicted_down": fn},
            "actual_down": {"predicted_up": fp, "predicted_down": tn},
        },
        "mcc": mcc,
        "wilson_accuracy_interval": _wilson_interval(correct, len(eligible)),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _rmse(errors: list[float]) -> float | None:
    if not errors:
        return None
    return round(math.sqrt(sum(error * error for error in errors) / len(errors)), 6)


def _average_ranks(values: list[float]) -> list[float]:
    indexed = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][0] == indexed[cursor][0]:
            end += 1
        rank = (cursor + 1 + end) / 2
        for _, original_index in indexed[cursor:end]:
            ranks[original_index] = rank
        cursor = end
    return ranks


def _spearman(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) < 2 or len(x_values) != len(y_values):
        return None
    x_ranks = _average_ranks(x_values)
    y_ranks = _average_ranks(y_values)
    mean_x = sum(x_ranks) / len(x_ranks)
    mean_y = sum(y_ranks) / len(y_ranks)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_ranks, y_ranks))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in x_ranks))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in y_ranks))
    if denom_x == 0 or denom_y == 0:
        return None
    return round(numerator / (denom_x * denom_y), 6)


def evaluate_numeric_forecast_error(rows: list[dict]) -> dict:
    """Evaluate numeric forecast error when predicted and actual returns are present."""

    normalized = normalize_forecast_actual_rows(rows)
    paired = [
        row
        for row in normalized
        if isinstance(row.get("predicted_return"), float) and isinstance(row.get("actual_return"), float)
    ]
    errors = [row["predicted_return"] - row["actual_return"] for row in paired]
    abs_errors = [abs(error) for error in errors]
    ape_values = [
        abs(row["predicted_return"] - row["actual_return"]) / abs(row["actual_return"])
        for row in paired
        if row["actual_return"] != 0
    ]
    smape_values = [
        2 * abs(row["predicted_return"] - row["actual_return"])
        / (abs(row["predicted_return"]) + abs(row["actual_return"]))
        for row in paired
        if abs(row["predicted_return"]) + abs(row["actual_return"]) != 0
    ]
    direction_hits = [
        _direction_from_return(row["predicted_return"]) == _direction_from_return(row["actual_return"])
        for row in paired
        if _direction_from_return(row["predicted_return"]) in BINARY_DIRECTIONS
        and _direction_from_return(row["actual_return"]) in BINARY_DIRECTIONS
    ]
    predicted = [row["predicted_return"] for row in paired]
    actual = [row["actual_return"] for row in paired]
    return {
        "sample_count": len(normalized),
        "numeric_coverage_count": len(paired),
        "mae": _mean(abs_errors),
        "rmse": _rmse(errors),
        "mape": _mean(ape_values),
        "smape": _mean(smape_values),
        "directional_hit_rate_from_returns": _ratio(sum(1 for hit in direction_hits if hit), len(direction_hits)),
        "mean_actual_return": _mean(actual),
        "mean_predicted_return": _mean(predicted),
        "spearman_rank_correlation": _spearman(predicted, actual),
    }


def evaluate_probability_metrics(rows: list[dict]) -> dict:
    """Evaluate probability metrics when a probability of an up direction is present."""

    normalized = normalize_forecast_actual_rows(rows)
    paired = [
        row
        for row in normalized
        if isinstance(row.get("predicted_probability"), float) and row.get("actual_direction") in BINARY_DIRECTIONS
    ]
    if not paired:
        return {
            "sample_count": len(normalized),
            "probability_coverage_count": 0,
            "brier_score": None,
            "log_loss": None,
            "calibration_bins": [],
        }
    brier_terms = []
    log_terms = []
    for row in paired:
        probability = min(max(row["predicted_probability"], 1e-15), 1 - 1e-15)
        actual = 1.0 if row["actual_direction"] == UP else 0.0
        brier_terms.append((probability - actual) ** 2)
        log_terms.append(-(actual * math.log(probability) + (1 - actual) * math.log(1 - probability)))
    bins: list[dict[str, Any]] = []
    if len(paired) >= 10:
        for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
            upper = lower + 0.2
            members = [
                row
                for row in paired
                if lower <= row["predicted_probability"] < upper or (upper == 1.0 and row["predicted_probability"] == 1.0)
            ]
            if not members:
                continue
            bins.append(
                {
                    "lower": round(lower, 2),
                    "upper": round(upper, 2),
                    "count": len(members),
                    "mean_probability": _mean([row["predicted_probability"] for row in members]),
                    "actual_up_rate": _ratio(sum(1 for row in members if row["actual_direction"] == UP), len(members)),
                }
            )
    return {
        "sample_count": len(normalized),
        "probability_coverage_count": len(paired),
        "brier_score": _mean(brier_terms),
        "log_loss": _mean(log_terms),
        "calibration_bins": bins,
    }


def _group_rows(rows: tuple[dict, ...], fields: tuple[str, ...]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = "|".join(f"{field}={row.get(field, 'unspecified')}" for field in fields)
        groups[key].append(row)
    return dict(groups)


def _subset_metrics(rows: list[dict]) -> dict:
    return {
        "directional": evaluate_directional_accuracy(rows),
        "numeric": evaluate_numeric_forecast_error(rows),
        "probability": evaluate_probability_metrics(rows),
    }


def _group_metrics(rows: tuple[dict, ...], fields: tuple[str, ...]) -> dict[str, dict]:
    return {key: _subset_metrics(group_rows) for key, group_rows in sorted(_group_rows(rows, fields).items())}


def _baseline_metrics(rows: tuple[dict, ...]) -> dict:
    eligible = _binary_rows(rows)
    positive_actual = sum(1 for row in eligible if row["actual_direction"] == UP)
    negative_actual = sum(1 for row in eligible if row["actual_direction"] == DOWN)
    majority = max(positive_actual, negative_actual)
    sorted_rows = sorted(rows, key=lambda row: (row["ticker"], row["horizon"], row["forecast_timestamp"], row["source_index"]))
    previous_correct = 0
    previous_count = 0
    previous_by_key: dict[tuple[str, str], str] = {}
    for row in sorted_rows:
        key = (row["ticker"], row["horizon"])
        actual = row.get("actual_direction")
        if actual in BINARY_DIRECTIONS and key in previous_by_key:
            previous_count += 1
            if previous_by_key[key] == actual:
                previous_correct += 1
        if actual in BINARY_DIRECTIONS:
            previous_by_key[key] = actual
    actual_returns = [row["actual_return"] for row in rows if isinstance(row.get("actual_return"), float)]
    return {
        "majority_class_baseline_accuracy": _ratio(majority, len(eligible)),
        "random_50_50_baseline_accuracy": 0.5 if eligible else None,
        "previous_direction_baseline_accuracy": _ratio(previous_correct, previous_count),
        "previous_direction_coverage_count": previous_count,
        "naive_zero_return_baseline": {
            "mae": _mean([abs(value) for value in actual_returns]),
            "rmse": _rmse(actual_returns),
            "sample_count": len(actual_returns),
        },
    }


def evaluate_forecast_accuracy(rows: list[dict]) -> dict:
    """Evaluate local forecast-vs-actual rows without external data or model execution."""

    normalized = normalize_forecast_actual_rows(rows)
    if not normalized:
        return {
            "accuracy_status": "not_ready_no_forecast_actual_rows",
            "evaluated_row_count": 0,
            "global": _subset_metrics([]),
            "groups": {
                "by_ticker": {},
                "by_horizon": {},
                "by_model_family": {},
                "by_model_id": {},
                "by_ticker_horizon": {},
                "by_model_horizon": {},
            },
            "baseline_comparison": _baseline_metrics(tuple()),
            "normalization": {"input_row_count": len(rows), "normalized_row_count": 0},
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
    return {
        "accuracy_status": "evaluated_local_forecast_actual_rows",
        "evaluated_row_count": len(normalized),
        "global": _subset_metrics(list(normalized)),
        "groups": {
            "by_ticker": _group_metrics(normalized, ("ticker",)),
            "by_horizon": _group_metrics(normalized, ("horizon",)),
            "by_model_family": _group_metrics(normalized, ("model_family",)),
            "by_model_id": _group_metrics(normalized, ("model_id",)),
            "by_ticker_horizon": _group_metrics(normalized, ("ticker", "horizon")),
            "by_model_horizon": _group_metrics(normalized, ("model_id", "horizon")),
        },
        "baseline_comparison": _baseline_metrics(normalized),
        "normalization": {"input_row_count": len(rows), "normalized_row_count": len(normalized)},
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _load_json_payload(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON input must be a list of objects or an object with rows")
    return rows


def load_forecast_accuracy_rows(path: str) -> list[dict[str, Any]]:
    """Load local rows from an explicit input path."""

    local_path = Path(path)
    if not local_path.exists() or not local_path.is_file():
        raise FileNotFoundError(f"forecast-actual input not found: {path}")
    suffix = local_path.suffix.lower()
    if suffix == ".csv":
        with local_path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".json":
        return _load_json_payload(local_path)
    if suffix == ".jsonl":
        rows = []
        for line in local_path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("JSONL input must contain objects")
                rows.append(row)
        return rows
    if suffix == ".parquet":
        try:
            import pandas as pd
        except ImportError as exc:
            raise ValueError("parquet input requires a local parquet engine") from exc
        return pd.read_parquet(local_path).to_dict(orient="records")
    raise ValueError("forecast-actual input must be .csv, .json, .jsonl, or .parquet")


def _fmt(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def render_forecast_accuracy_report(result: dict) -> str:
    """Render a public-safe local accuracy report."""

    directional = (result.get("global") or {}).get("directional", {})
    numeric = (result.get("global") or {}).get("numeric", {})
    probability = (result.get("global") or {}).get("probability", {})
    baseline = result.get("baseline_comparison") or {}
    lines = [
        "# Forecast-vs-Actual Accuracy Evaluation",
        "",
        f"Accuracy status: {result.get('accuracy_status')}",
        f"Evaluated rows: {result.get('evaluated_row_count')}",
        "",
        "Directional metrics:",
        f"- coverage_count: {_fmt(directional.get('coverage_count'))}",
        f"- accuracy: {_fmt(directional.get('accuracy'))}",
        f"- balanced_accuracy: {_fmt(directional.get('balanced_accuracy'))}",
        f"- MCC: {_fmt(directional.get('mcc'))}",
        f"- Wilson interval: {directional.get('wilson_accuracy_interval')}",
        f"- confusion_matrix: {directional.get('confusion_matrix')}",
        "",
        "Numeric metrics:",
        f"- MAE: {_fmt(numeric.get('mae'))}",
        f"- RMSE: {_fmt(numeric.get('rmse'))}",
        f"- sMAPE: {_fmt(numeric.get('smape'))}",
        f"- return-direction hit rate: {_fmt(numeric.get('directional_hit_rate_from_returns'))}",
        "",
        "Probability metrics:",
        f"- Brier score: {_fmt(probability.get('brier_score'))}",
        f"- log loss: {_fmt(probability.get('log_loss'))}",
        f"- probability coverage: {_fmt(probability.get('probability_coverage_count'))}",
        "",
        "Baselines:",
        f"- majority class: {_fmt(baseline.get('majority_class_baseline_accuracy'))}",
        f"- random 50/50: {_fmt(baseline.get('random_50_50_baseline_accuracy'))}",
        f"- previous direction: {_fmt(baseline.get('previous_direction_baseline_accuracy'))}",
        f"- zero-return MAE: {_fmt((baseline.get('naive_zero_return_baseline') or {}).get('mae'))}",
        "",
        "Boundary:",
        "Accuracy is computed only from explicit local forecast-vs-actual rows.",
        "No external data access, model execution, model update, or market-action output is performed.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate explicit local forecast-vs-actual rows.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.input and args.discover:
        parser.error("--input and --discover are mutually exclusive")
    try:
        if args.discover:
            discovery = discover_forecast_actual_artifacts(repo_root=".")
            result = {
                "accuracy_status": "not_ready_no_forecast_actual_rows",
                "evaluated_row_count": 0,
                "discovery": discovery,
                "global": _subset_metrics([]),
                "baseline_comparison": _baseline_metrics(tuple()),
                "claim_boundary": dict(CLAIM_BOUNDARY),
                "non_claim": "Discovery-only dry report; pass --input to compute accuracy from explicit rows.",
                "human_review_required": True,
            }
        else:
            rows = load_forecast_accuracy_rows(args.input) if args.input else []
            result = evaluate_forecast_accuracy(rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.format == "report":
        print(render_forecast_accuracy_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
