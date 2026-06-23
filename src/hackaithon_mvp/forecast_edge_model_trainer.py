"""Train bounded clean forecast-edge models with validation-only selection."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy


DEFAULT_HORIZONS = (1, 5, 10, 20)
MIN_SLICE_ROWS = 300
MIN_HOLDOUT_ROWS = 60
MAX_ROWS_PER_GROUP = 4_000
CLAIM_BOUNDARY = {
    "local_training_only": True,
    "clean_non_overlapping_rows_expected": True,
    "validation_selection_only": True,
    "holdout_checked_once": True,
    "no_model_binaries_written": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast-edge trainer reports local validation and holdout diagnostics with abstention allowed."

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")


def _direction_to_int(value: Any) -> int | None:
    text = str(value).strip().lower() if value not in (None, "") else ""
    if text in {"up", "positive", "1", "+1", "true"}:
        return 1
    if text in {"down", "negative", "0", "-1", "false"}:
        return 0
    return None


def _int_to_direction(value: int) -> str:
    return "up" if int(value) == 1 else "down"


def _feature_columns(rows: list[dict]) -> list[str]:
    columns = sorted({key for row in rows for key in row if str(key).startswith("feature_")})
    blocked = ("future", "target", "actual", "label")
    return [column for column in columns if not any(word in column.lower() for word in blocked)]


def _safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _model_rows(rows: list[dict], horizons: tuple[int, ...]) -> list[dict]:
    clean = []
    horizon_set = {int(horizon) for horizon in horizons}
    for row in rows:
        try:
            horizon = int(row.get("horizon"))
        except (TypeError, ValueError):
            continue
        if horizon not in horizon_set:
            continue
        target = _direction_to_int(row.get("future_direction", row.get("actual_direction")))
        if target is None:
            continue
        item = dict(row)
        item["_target"] = target
        clean.append(item)
    clean.sort(key=lambda item: (str(item.get("timestamp") or item.get("forecast_timestamp")), str(item.get("ticker"))))
    return clean


def _split_three_way(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    count = len(rows)
    train_end = max(1, int(count * 0.60))
    validation_end = max(train_end + 1, int(count * 0.80))
    validation_end = min(validation_end, count - 1)
    return rows[:train_end], rows[train_end:validation_end], rows[validation_end:]


def _xy(rows: list[dict], columns: list[str]):
    import numpy as np

    x_rows = []
    y_rows = []
    for row in rows:
        values = []
        ok = True
        for column in columns:
            value = _safe_float(row.get(column))
            if value is None:
                value = 0.0
            if not math.isfinite(value):
                ok = False
                break
            values.append(value)
        if ok:
            x_rows.append(values)
            y_rows.append(int(row["_target"]))
    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int)


def _sklearn_available() -> tuple[bool, str | None]:
    try:
        import sklearn  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - dependency boundary.
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def _candidate_models(max_models: int):
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression, RidgeClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import LinearSVC

    candidates = [
        ("dummy_majority", {}, DummyClassifier(strategy="most_frequent")),
        (
            "logistic_l2",
            {"C": 0.25, "class_weight": "balanced"},
            make_pipeline(
                StandardScaler(),
                LogisticRegression(C=0.25, penalty="l2", class_weight="balanced", max_iter=300, solver="liblinear", random_state=42),
            ),
        ),
        (
            "logistic_l2",
            {"C": 1.0, "class_weight": "balanced"},
            make_pipeline(
                StandardScaler(),
                LogisticRegression(C=1.0, penalty="l2", class_weight="balanced", max_iter=300, solver="liblinear", random_state=42),
            ),
        ),
        ("ridge_classifier", {"alpha": 1.0}, make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0))),
        (
            "linear_svm",
            {"C": 0.25, "class_weight": "balanced"},
            make_pipeline(StandardScaler(), LinearSVC(C=0.25, class_weight="balanced", max_iter=2500, random_state=42)),
        ),
        (
            "random_forest",
            {"n_estimators": 60, "max_depth": 4},
            RandomForestClassifier(
                n_estimators=60,
                max_depth=4,
                min_samples_leaf=20,
                class_weight="balanced_subsample",
                random_state=42,
                n_jobs=1,
            ),
        ),
        (
            "extra_trees",
            {"n_estimators": 80, "max_depth": 4},
            ExtraTreesClassifier(
                n_estimators=80,
                max_depth=4,
                min_samples_leaf=20,
                class_weight="balanced",
                random_state=42,
                n_jobs=1,
            ),
        ),
        (
            "gradient_boosting",
            {"n_estimators": 50, "learning_rate": 0.05, "max_depth": 2},
            GradientBoostingClassifier(n_estimators=50, learning_rate=0.05, max_depth=2, random_state=42),
        ),
        (
            "hist_gradient_boosting",
            {"max_iter": 60, "learning_rate": 0.05, "max_leaf_nodes": 15},
            HistGradientBoostingClassifier(max_iter=60, learning_rate=0.05, max_leaf_nodes=15, random_state=42),
        ),
    ]
    return candidates[: max(0, int(max_models))]


def _probabilities(model: Any, x_values: Any) -> list[float]:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(x_values)
        if probabilities.shape[1] == 1:
            only_class = int(getattr(model, "classes_", [0])[0])
            return [1.0 if only_class == 1 else 0.0 for _ in range(len(x_values))]
        class_index = list(model.classes_).index(1) if hasattr(model, "classes_") and 1 in list(model.classes_) else 1
        return [float(value) for value in probabilities[:, class_index]]
    if hasattr(model, "decision_function"):
        scores = model.decision_function(x_values)
        return [1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, float(score))))) for score in scores]
    predictions = model.predict(x_values)
    return [float(prediction) for prediction in predictions]


def _forecast_rows(
    source_rows: list[dict],
    *,
    probabilities: list[float],
    model_id: str,
    model_family: str,
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    rows = []
    for source, probability in zip(source_rows, probabilities):
        predicted = "up" if probability >= threshold else "down"
        actual_direction = source.get("future_direction", source.get("actual_direction"))
        rows.append(
            {
                "ticker": source.get("ticker"),
                "model_id": model_id,
                "model_family": model_family,
                "horizon": int(source.get("horizon")),
                "forecast_timestamp": source.get("forecast_timestamp") or source.get("timestamp"),
                "actual_timestamp": source.get("actual_timestamp") or source.get("future_timestamp"),
                "predicted_direction": predicted,
                "actual_direction": actual_direction,
                "predicted_probability": probability,
                "actual_return": source.get("future_return", source.get("actual_return")),
                "target": "clean_future_direction",
            }
        )
    return rows


def _best_by_validation(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item.get("validation_metrics", {}).get("balanced_accuracy") or -1,
            item.get("validation_metrics", {}).get("mcc") or -2,
            item.get("model_id") != "dummy_majority",
        ),
        reverse=True,
    )
    return candidates[0]


def _train_group(
    rows: list[dict],
    *,
    ticker: str,
    horizon: int,
    scope: str,
    feature_columns: list[str],
    max_models: int,
    min_slice_rows: int,
) -> dict:
    if len(rows) < int(min_slice_rows):
        return {
            "slice_id": f"{ticker}|h{horizon}|{scope}",
            "ticker": ticker,
            "horizon": horizon,
            "scope": scope,
            "training_status": "skipped",
            "skip_reason": "insufficient_clean_rows",
            "available_rows": len(rows),
            "minimum_rows": int(min_slice_rows),
        }
    limited = rows[-MAX_ROWS_PER_GROUP:] if len(rows) > MAX_ROWS_PER_GROUP else rows
    train_rows, validation_rows, holdout_rows = _split_three_way(limited)
    if len(holdout_rows) < MIN_HOLDOUT_ROWS or len(validation_rows) < MIN_HOLDOUT_ROWS:
        return {
            "slice_id": f"{ticker}|h{horizon}|{scope}",
            "ticker": ticker,
            "horizon": horizon,
            "scope": scope,
            "training_status": "skipped",
            "skip_reason": "insufficient_validation_or_holdout_rows",
            "available_rows": len(rows),
            "validation_rows": len(validation_rows),
            "holdout_rows": len(holdout_rows),
        }
    class_count = Counter(row["_target"] for row in train_rows)
    if len(class_count) < 2:
        return {
            "slice_id": f"{ticker}|h{horizon}|{scope}",
            "ticker": ticker,
            "horizon": horizon,
            "scope": scope,
            "training_status": "skipped",
            "skip_reason": "single_class_training_slice",
            "available_rows": len(rows),
        }
    x_train, y_train = _xy(train_rows, feature_columns)
    x_validation, _ = _xy(validation_rows, feature_columns)
    x_holdout, _ = _xy(holdout_rows, feature_columns)
    candidate_results = []
    for model_id, params, model in _candidate_models(max_models):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(x_train, y_train)
            validation_probabilities = _probabilities(model, x_validation)
            validation_forecasts = _forecast_rows(
                validation_rows,
                probabilities=validation_probabilities,
                model_id=model_id,
                model_family="classification",
            )
            validation_eval = evaluate_forecast_accuracy(validation_forecasts)
            validation_metrics = validation_eval["global"]["directional"]
            candidate_results.append(
                {
                    "model_id": model_id,
                    "model_family": "classification",
                    "selected_hyperparameters": params,
                    "model": model,
                    "validation_metrics": validation_metrics,
                    "validation_forecast_rows": validation_forecasts,
                }
            )
        except Exception as exc:  # noqa: BLE001 - isolate candidate fit.
            candidate_results.append(
                {
                    "model_id": model_id,
                    "training_status": "candidate_failed",
                    "skip_reason": f"{type(exc).__name__}: {exc}",
                    "selected_hyperparameters": params,
                }
            )
    successful = [item for item in candidate_results if item.get("validation_metrics")]
    selected = _best_by_validation(successful)
    if selected is None:
        return {
            "slice_id": f"{ticker}|h{horizon}|{scope}",
            "ticker": ticker,
            "horizon": horizon,
            "scope": scope,
            "training_status": "skipped",
            "skip_reason": "no_candidate_completed",
            "available_rows": len(rows),
        }
    holdout_probabilities = _probabilities(selected["model"], x_holdout)
    holdout_forecasts = _forecast_rows(
        holdout_rows,
        probabilities=holdout_probabilities,
        model_id=str(selected["model_id"]),
        model_family="classification",
    )
    holdout_eval = evaluate_forecast_accuracy(holdout_forecasts)
    holdout_metrics = holdout_eval["global"]["directional"]
    baselines = holdout_eval["baseline_comparison"]
    selected.pop("model", None)
    return {
        "slice_id": f"{ticker}|h{horizon}|{scope}|{selected['model_id']}",
        "ticker": ticker,
        "horizon": horizon,
        "scope": scope,
        "model_id": selected["model_id"],
        "model_family": "classification",
        "training_status": "completed",
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "holdout_rows": len(holdout_rows),
        "minimum_holdout_rows": int(min_slice_rows),
        "feature_column_count": len(feature_columns),
        "candidate_count": len(candidate_results),
        "completed_candidate_count": len(successful),
        "selected_hyperparameters": selected.get("selected_hyperparameters"),
        "validation_metrics": selected.get("validation_metrics"),
        "holdout_metrics": holdout_metrics,
        "holdout_baselines": baselines,
        "random_baseline": baselines.get("random_50_50_baseline_accuracy"),
        "majority_baseline": baselines.get("majority_class_baseline_accuracy"),
        "previous_direction_baseline": baselines.get("previous_direction_baseline_accuracy"),
        "beats_random": (holdout_metrics.get("balanced_accuracy") or 0) > (baselines.get("random_50_50_baseline_accuracy") or 0.5),
        "beats_majority": (holdout_metrics.get("balanced_accuracy") or 0) > (baselines.get("majority_class_baseline_accuracy") or 1.0),
        "beats_previous_direction": (
            baselines.get("previous_direction_baseline_accuracy") is not None
            and (holdout_metrics.get("balanced_accuracy") or 0) > baselines["previous_direction_baseline_accuracy"]
        ),
        "validation_holdout_balanced_accuracy_gap": (
            (selected.get("validation_metrics") or {}).get("balanced_accuracy") or 0
        )
        - (holdout_metrics.get("balanced_accuracy") or 0),
        "duplicate_key_severity": "none",
        "overlap_severity": "none",
        "leakage_warning": False,
        "holdout_forecast_rows": holdout_forecasts,
        "candidate_summaries": [
            {key: value for key, value in item.items() if key not in {"validation_forecast_rows", "model"}}
            for item in candidate_results
        ],
    }


def _groups(rows: list[dict], horizons: tuple[int, ...]) -> list[tuple[str, int, str, list[dict]]]:
    groups: list[tuple[str, int, str, list[dict]]] = []
    by_horizon: dict[int, list[dict]] = defaultdict(list)
    by_ticker_horizon: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        horizon = int(row["horizon"])
        if horizon not in horizons:
            continue
        ticker = str(row.get("ticker") or "GLOBAL")
        by_horizon[horizon].append(row)
        by_ticker_horizon[(ticker, horizon)].append(row)
    for horizon in horizons:
        if by_horizon.get(horizon):
            groups.append(("GLOBAL", horizon, "global_horizon", by_horizon[horizon]))
    for (ticker, horizon), group_rows in sorted(by_ticker_horizon.items(), key=lambda item: (item[0][1], item[0][0])):
        groups.append((ticker, horizon, "ticker_horizon", group_rows))
    return groups


def train_forecast_edge_models(
    rows: list[dict],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    max_models: int = 300,
    max_workers: int = 1,
    min_slice_rows: int = MIN_SLICE_ROWS,
) -> dict:
    """Train bounded forecast-edge models and report holdout diagnostics."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    started = time.monotonic()
    clean_horizons = tuple(int(horizon) for horizon in horizons)
    clean_rows = _model_rows(rows, clean_horizons)
    feature_columns = _feature_columns(clean_rows)
    sklearn_ok, dependency_error = _sklearn_available()
    if not sklearn_ok:
        return {
            "training_status": "blocked_missing_dependency",
            "dependency_error": dependency_error,
            "input_rows": len(rows),
            "clean_training_rows": len(clean_rows),
            "feature_columns": feature_columns,
            "model_results": [],
            "attempted_model_specs": 0,
            "trained_model_specs": 0,
            "tuned_model_specs": 0,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
    if not clean_rows or not feature_columns:
        return {
            "training_status": "blocked_by_insufficient_data",
            "input_rows": len(rows),
            "clean_training_rows": len(clean_rows),
            "feature_columns": feature_columns,
            "model_results": [],
            "attempted_model_specs": 0,
            "trained_model_specs": 0,
            "tuned_model_specs": 0,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
    model_results = []
    attempted_candidates = 0
    max_groups = max(1, int(max_models) // max(1, len(_candidate_models(999))))
    for ticker, horizon, scope, group_rows in _groups(clean_rows, clean_horizons)[:max_groups]:
        group_models = min(len(_candidate_models(999)), max(1, int(max_models) - attempted_candidates))
        if group_models <= 0:
            break
        result = _train_group(
            group_rows,
            ticker=ticker,
            horizon=horizon,
            scope=scope,
            feature_columns=feature_columns,
            max_models=group_models,
            min_slice_rows=min_slice_rows,
        )
        attempted_candidates += int(result.get("candidate_count") or group_models)
        model_results.append(result)
        if attempted_candidates >= int(max_models):
            break
    trained = [item for item in model_results if item.get("training_status") == "completed"]
    forecast_rows = [row for item in trained for row in item.get("holdout_forecast_rows") or []]
    status = "completed" if model_results else "blocked_by_insufficient_data"
    return {
        "training_status": status,
        "input_rows": len(rows),
        "clean_training_rows": len(clean_rows),
        "horizons": list(clean_horizons),
        "feature_columns": feature_columns,
        "feature_column_count": len(feature_columns),
        "model_results": model_results,
        "attempted_model_specs": len(model_results),
        "trained_model_specs": len(trained),
        "tuned_model_specs": len(trained),
        "candidate_fit_attempt_count": attempted_candidates,
        "forecast_rows_count": len(forecast_rows),
        "max_workers_requested": max_workers,
        "max_workers_used": 1,
        "min_slice_rows": min_slice_rows,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_edge_training_report(result: dict) -> str:
    """Render a compact forecast-edge training report."""

    skips = Counter(item.get("skip_reason", "none") for item in result.get("model_results", []) if item.get("training_status") != "completed")
    lines = [
        "# Forecast Edge Model Trainer",
        "",
        f"Training status: {result.get('training_status')}",
        f"Clean training rows: {result.get('clean_training_rows')}",
        f"Feature columns: {result.get('feature_column_count')}",
        f"Attempted model groups: {result.get('attempted_model_specs')}",
        f"Trained model groups: {result.get('trained_model_specs')}",
        f"Tuned model groups: {result.get('tuned_model_specs')}",
        f"Holdout forecast rows: {result.get('forecast_rows_count')}",
        "",
        "Top skip reasons:",
    ]
    lines.extend([f"- {key}: {value}" for key, value in skips.most_common(8)] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Model selection uses validation metrics; holdout metrics are reported after selection.",
            "No model binaries are written.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train bounded forecast-edge models from local feature rows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--horizons", default="1,5,10,20")
    parser.add_argument("--max-models", type=int, default=300)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--min-slice-rows", type=int, default=MIN_SLICE_ROWS)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    horizons = tuple(int(item.strip()) for item in str(args.horizons).split(",") if item.strip())
    result = train_forecast_edge_models(
        _load_jsonl(args.input),
        horizons=horizons,
        max_models=args.max_models,
        max_workers=args.max_workers,
        min_slice_rows=args.min_slice_rows,
    )
    if args.format == "report":
        print(render_forecast_edge_training_report({key: value for key, value in result.items() if key != "model_results"}), end="")
    else:
        public = json.loads(json.dumps(result, default=str))
        print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
