"""Train and tune eligible local baseline model groups."""

from __future__ import annotations

import argparse
import json
import math
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy
from src.hackaithon_mvp.model_diagnostics.registry import get_adapter
from src.hackaithon_mvp.purged_walk_forward_validation import purged_temporal_split


SUPPORTED_CLASSIFICATION_MODELS = {
    "majority_class",
    "previous_direction",
    "logistic_l1",
    "logistic_l2",
    "ridge_classifier",
    "random_forest",
    "extra_trees",
    "linear_svm",
    "sklearn_gradient_boosting",
    "hist_gradient_boosting",
}
SUPPORTED_REGRESSION_MODELS = {"linear_regression", "ridge_regression", "random_forest_regressor"}
SUPPORTED_DIRECTION_TARGETS = {"absolute_direction", "return_direction", "market_relative_direction"}
SUPPORTED_RETURN_TARGETS = {"forward_return", "volatility_adjusted_return"}
THRESHOLD_CANDIDATES = tuple(round(0.45 + index * 0.01, 2) for index in range(11))
MAX_ROWS_PER_MODEL = 2_500
MIN_ROWS_PER_MODEL = 120
MIN_VALIDATION_ROWS = 30
CLAIM_BOUNDARY = {
    "local_training_only": True,
    "writes_require_output_root": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_binaries_written": True,
    "temporal_validation": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local training run over generated supervised rows; validation metrics are evidence, not deployment claims."


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    allowed = (".tmp_full_model_run", ".tmp_performance_rescue", ".tmp_accuracy_maximization")
    if not any(part.lower().startswith(allowed) for part in root.parts):
        raise ValueError("output_root must be an explicit local temp model-run root or a child path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _compatible_spec(spec) -> tuple[bool, str | None]:
    if spec.model_key in SUPPORTED_CLASSIFICATION_MODELS:
        if spec.target in SUPPORTED_DIRECTION_TARGETS:
            return True, None
        return False, "target_not_supported_by_classifier"
    if spec.model_key in SUPPORTED_REGRESSION_MODELS:
        if spec.target in SUPPORTED_RETURN_TARGETS:
            return True, None
        return False, "target_not_supported_by_regressor"
    return False, "model_wrapper_not_supported"


def discover_trainable_model_specs() -> dict:
    """Discover deduplicated trainable baseline model groups."""

    groups: dict[tuple[str, str, int], dict[str, Any]] = {}
    skipped = Counter()
    for spec in generate_baseline_catalog():
        ok, reason = _compatible_spec(spec)
        if not ok:
            skipped[str(reason)] += 1
            continue
        key = (str(spec.model_key), str(spec.target), int(spec.horizon))
        groups.setdefault(
            key,
            {
                "model_key": spec.model_key,
                "model_family": spec.model_family,
                "target": spec.target,
                "horizon": spec.horizon,
                "representative_engine_id": spec.engine_id,
            },
        )
    return {
        "discovery_status": "completed",
        "trainable_model_spec_count": len(groups),
        "trainable_model_specs": list(groups.values()),
        "skipped_specs_by_reason": dict(sorted(skipped.items())),
        "supported_model_keys": sorted(SUPPORTED_CLASSIFICATION_MODELS | SUPPORTED_REGRESSION_MODELS),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _target_value(row: dict, target: str) -> float | int | None:
    if target in {"absolute_direction", "return_direction"}:
        direction = row.get("future_direction")
        if direction == "up":
            return 1
        if direction == "down":
            return 0
        return None
    if target == "market_relative_direction":
        direction = row.get("market_relative_direction")
        if direction == "up":
            return 1
        if direction == "down":
            return 0
        return None
    if target == "forward_return":
        return float(row["future_return"]) if row.get("future_return") is not None else None
    if target == "volatility_adjusted_return":
        return float(row["volatility_adjusted_future_return"]) if row.get("volatility_adjusted_future_return") is not None else None
    return None


def _feature_columns(rows: list[dict]) -> list[str]:
    columns = sorted({key for row in rows for key in row if key.startswith("feature_")})
    return columns


def _rows_for_spec(spec: dict, dataset_rows: list[dict]) -> list[dict]:
    horizon = int(spec["horizon"])
    target = str(spec["target"])
    rows = []
    for row in dataset_rows:
        if int(row.get("horizon", -1)) != horizon:
            continue
        value = _target_value(row, target)
        if value is None:
            continue
        output = dict(row)
        output["_target_value"] = value
        rows.append(output)
    rows.sort(key=lambda item: (str(item.get("timestamp")), str(item.get("ticker"))))
    if len(rows) > MAX_ROWS_PER_MODEL:
        rows = rows[-MAX_ROWS_PER_MODEL:]
    return rows


def _temporal_split(rows: list[dict], train_fraction: float = 0.7) -> tuple[list[dict], list[dict]]:
    if len(rows) < 2:
        return rows, []
    split_index = int(len(rows) * train_fraction)
    split_index = min(max(split_index, 1), len(rows) - 1)
    return rows[:split_index], rows[split_index:]


def _purged_or_temporal_split(rows: list[dict], horizon_steps: int) -> tuple[list[dict], list[dict], dict]:
    split = purged_temporal_split(rows, horizon_steps=horizon_steps, validation_fraction=0.3)
    if split.get("split_status") == "ready" and int(split.get("validation_row_count") or 0) >= MIN_VALIDATION_ROWS:
        return list(split["train_rows"]), list(split["validation_rows"]), {
            "split_method": "purged_temporal",
            "purged_row_count": split.get("purged_row_count"),
            "embargoed_row_count": split.get("embargoed_row_count"),
        }
    train_rows, validation_rows = _temporal_split(rows)
    return train_rows, validation_rows, {
        "split_method": "temporal_fallback_after_purge",
        "purged_row_count": split.get("purged_row_count"),
        "embargoed_row_count": split.get("embargoed_row_count"),
        "purged_split_status": split.get("split_status"),
    }


def _inner_split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(rows) < 4:
        return rows, rows
    split_index = int(len(rows) * 0.75)
    split_index = min(max(split_index, 1), len(rows) - 1)
    return rows[:split_index], rows[split_index:]


def _xy(rows: list[dict], feature_columns: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x_values = [[float(row.get(column, 0.0) or 0.0) for column in feature_columns] for row in rows]
    y_values = [row["_target_value"] for row in rows]
    return np.asarray(x_values, dtype=float), np.asarray(y_values)


def _classification_metric(y_true: list[int], y_pred: list[int]) -> dict:
    forecast_rows = [
        {
            "ticker": str(index),
            "predicted_direction": "up" if pred else "down",
            "actual_direction": "up" if actual else "down",
        }
        for index, (actual, pred) in enumerate(zip(y_true, y_pred))
    ]
    directional = evaluate_forecast_accuracy(forecast_rows)["global"]["directional"]
    return {
        "accuracy": directional["accuracy"],
        "balanced_accuracy": directional["balanced_accuracy"],
        "mcc": directional["mcc"],
        "coverage_count": directional["coverage_count"],
    }


def _regression_metric(y_true: list[float], y_pred: list[float]) -> dict:
    forecast_rows = [
        {
            "ticker": str(index),
            "predicted_return": pred,
            "actual_return": actual,
        }
        for index, (actual, pred) in enumerate(zip(y_true, y_pred))
    ]
    result = evaluate_forecast_accuracy(forecast_rows)
    return {
        "mae": result["global"]["numeric"]["mae"],
        "rmse": result["global"]["numeric"]["rmse"],
        "directional_accuracy": result["global"]["directional"]["accuracy"],
        "balanced_accuracy": result["global"]["directional"]["balanced_accuracy"],
    }


def _threshold_from_probabilities(y_true: list[int], probabilities: list[float]) -> tuple[float, dict]:
    best_threshold = 0.5
    best_metric = -1.0
    best_result: dict[str, Any] = {}
    for threshold in THRESHOLD_CANDIDATES:
        preds = [1 if value >= threshold else 0 for value in probabilities]
        metric = _classification_metric(y_true, preds)
        score = metric["balanced_accuracy"] if metric["balanced_accuracy"] is not None else -1.0
        if score > best_metric:
            best_metric = float(score)
            best_threshold = threshold
            best_result = metric
    return best_threshold, best_result


def _sklearn_available() -> tuple[bool, str | None]:
    try:
        import sklearn  # noqa: F401

        return True, None
    except ImportError as exc:
        return False, type(exc).__name__


def _classification_candidates(model_key: str):
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression, RidgeClassifier
    from sklearn.svm import LinearSVC
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if model_key == "majority_class":
        return [({"strategy": "most_frequent"}, DummyClassifier(strategy="most_frequent"))]
    if model_key == "logistic_l2":
        return [
            (
                {"C": c, "penalty": "l2", "class_weight": class_weight},
                make_pipeline(
                    StandardScaler(),
                    LogisticRegression(C=c, penalty="l2", class_weight=class_weight, max_iter=250, solver="liblinear"),
                ),
            )
            for c in (0.01, 0.1, 1.0, 10.0)
            for class_weight in (None, "balanced")
        ]
    if model_key == "logistic_l1":
        return [
            (
                {"C": c, "penalty": "l1", "class_weight": class_weight},
                make_pipeline(
                    StandardScaler(),
                    LogisticRegression(C=c, penalty="l1", class_weight=class_weight, max_iter=250, solver="liblinear"),
                ),
            )
            for c in (0.01, 0.1, 1.0, 10.0)
            for class_weight in (None, "balanced")
        ]
    if model_key == "linear_svm":
        return [
            (
                {"C": c, "class_weight": class_weight},
                make_pipeline(StandardScaler(), LinearSVC(C=c, class_weight=class_weight, max_iter=2000, random_state=42)),
            )
            for c in (0.01, 0.1, 1.0)
            for class_weight in (None, "balanced")
        ]
    if model_key == "ridge_classifier":
        return [({"alpha": a}, make_pipeline(StandardScaler(), RidgeClassifier(alpha=a))) for a in (0.1, 1.0, 10.0)]
    if model_key == "random_forest":
        return [
            (
                {"n_estimators": n_estimators, "max_depth": depth, "min_samples_leaf": leaf, "class_weight": class_weight},
                RandomForestClassifier(
                    n_estimators=n_estimators,
                    max_depth=depth,
                    min_samples_leaf=leaf,
                    class_weight=class_weight,
                    random_state=42,
                    n_jobs=1,
                ),
            )
            for n_estimators in (100, 200)
            for depth in (3, 5, 8, None)
            for leaf in (5, 20, 50)
            for class_weight in (None, "balanced")
        ]
    if model_key == "extra_trees":
        return [
            (
                {"n_estimators": n_estimators, "max_depth": depth, "min_samples_leaf": leaf, "class_weight": class_weight},
                ExtraTreesClassifier(
                    n_estimators=n_estimators,
                    max_depth=depth,
                    min_samples_leaf=leaf,
                    class_weight=class_weight,
                    random_state=42,
                    n_jobs=1,
                ),
            )
            for n_estimators in (100, 200)
            for depth in (3, 5, 8, None)
            for leaf in (5, 20, 50)
            for class_weight in (None, "balanced")
        ]
    if model_key == "sklearn_gradient_boosting":
        return [
            (
                {"n_estimators": n_estimators, "learning_rate": lr, "max_depth": depth},
                GradientBoostingClassifier(n_estimators=n_estimators, learning_rate=lr, max_depth=depth, random_state=42),
            )
            for lr in (0.01, 0.03, 0.05)
            for n_estimators in (100, 200)
            for depth in (2, 3)
        ]
    if model_key == "hist_gradient_boosting":
        return [
            (
                {"learning_rate": lr, "max_leaf_nodes": leaves, "l2_regularization": l2},
                HistGradientBoostingClassifier(
                    max_iter=100,
                    learning_rate=lr,
                    max_leaf_nodes=leaves,
                    l2_regularization=l2,
                    random_state=42,
                ),
            )
            for lr in (0.01, 0.03, 0.05)
            for leaves in (15, 31)
            for l2 in (0.0, 0.1, 1.0)
        ]
    return []


def _regression_candidates(model_key: str):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if model_key == "linear_regression":
        return [({}, make_pipeline(StandardScaler(), LinearRegression()))]
    if model_key == "ridge_regression":
        return [({"alpha": a}, make_pipeline(StandardScaler(), Ridge(alpha=a))) for a in (0.1, 1.0, 10.0)]
    if model_key == "random_forest_regressor":
        return [
            (
                {"n_estimators": n_estimators, "max_depth": depth, "min_samples_leaf": leaf},
                RandomForestRegressor(
                    n_estimators=n_estimators,
                    max_depth=depth,
                    min_samples_leaf=leaf,
                    random_state=42,
                    n_jobs=1,
                ),
            )
            for n_estimators in (100, 200)
            for depth in (3, 5, 8, None)
            for leaf in (5, 20, 50)
        ]
    return []


def _positive_scores(model: Any, x_values: np.ndarray) -> list[float]:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(x_values)
        if proba.shape[1] == 1:
            return [float(proba[index, 0]) for index in range(proba.shape[0])]
        return [float(value) for value in proba[:, 1]]
    if hasattr(model, "decision_function"):
        values = model.decision_function(x_values)
        return [float(1.0 / (1.0 + math.exp(-max(min(float(value), 20.0), -20.0)))) for value in values]
    preds = model.predict(x_values)
    return [float(value) for value in preds]


def _previous_direction_predict(rows: list[dict]) -> list[int]:
    return [1 if float(row.get("feature_lag_return_1", 0.0) or 0.0) >= 0 else 0 for row in rows]


def tune_one_model_spec(
    spec: dict,
    train_rows: list[dict],
    validation_rows: list[dict],
    *,
    timeout_seconds: int | None = None,
) -> dict:
    """Fit bounded candidates on train rows and report validation metrics."""

    started = time.monotonic()
    model_key = str(spec["model_key"])
    target = str(spec["target"])
    feature_columns = _feature_columns(train_rows + validation_rows)
    if not feature_columns and model_key != "previous_direction":
        return {"tuning_status": "skipped", "skip_reason": "feature_columns_missing"}
    if len({row["_target_value"] for row in train_rows}) < 2 and model_key not in {"majority_class"} | SUPPORTED_REGRESSION_MODELS:
        return {"tuning_status": "skipped", "skip_reason": "single_class_train_split"}
    if model_key == "previous_direction":
        y_val = [int(row["_target_value"]) for row in validation_rows]
        pre_preds = _previous_direction_predict(validation_rows)
        metric = _classification_metric(y_val, pre_preds)
        return {
            "tuning_status": "completed",
            "selected_hyperparameters": {"policy": "previous_direction"},
            "selected_threshold": None,
            "pre_tune_validation_metrics": metric,
            "post_tune_validation_metrics": metric,
            "supports_probability": False,
            "model_object": None,
        }

    sklearn_ok, dependency_error = _sklearn_available()
    if not sklearn_ok:
        return {"tuning_status": "skipped", "skip_reason": "dependency_unavailable", "dependency_error": dependency_error}

    is_classifier = model_key in SUPPORTED_CLASSIFICATION_MODELS
    candidates = _classification_candidates(model_key) if is_classifier else _regression_candidates(model_key)
    if not candidates:
        return {"tuning_status": "skipped", "skip_reason": "model_wrapper_not_supported"}
    inner_train, inner_calibration = _inner_split(train_rows)
    x_inner, y_inner = _xy(inner_train, feature_columns)
    x_cal, y_cal = _xy(inner_calibration, feature_columns)
    candidate_results: list[dict[str, Any]] = []
    search_stopped_early = False
    for params, model in candidates:
        if timeout_seconds is not None and candidate_results and time.monotonic() - started >= timeout_seconds:
            search_stopped_early = True
            break
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
                warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
                model.fit(x_inner, y_inner)
            if is_classifier:
                scores = _positive_scores(model, x_cal)
                threshold, train_metric = _threshold_from_probabilities([int(value) for value in y_cal], scores)
                objective = train_metric.get("balanced_accuracy")
                secondary = train_metric.get("mcc")
            else:
                preds = [float(value) for value in model.predict(x_cal)]
                train_metric = _regression_metric([float(value) for value in y_cal], preds)
                threshold = 0.0
                objective = -(train_metric.get("rmse") or 999.0)
                secondary = train_metric.get("balanced_accuracy")
            candidate_results.append(
                {
                    "params": params,
                    "model": model,
                    "threshold": threshold,
                    "inner_metric": train_metric,
                    "objective": objective if objective is not None else -999.0,
                    "secondary_objective": secondary if secondary is not None else -999.0,
                    "tertiary_objective": train_metric.get("accuracy") if is_classifier else train_metric.get("directional_accuracy"),
                }
            )
        except Exception as exc:  # noqa: BLE001 - per-model isolation.
            candidate_results.append({"params": params, "error": type(exc).__name__, "objective": -999.0})
    selectable = [item for item in candidate_results if "model" in item]
    if not selectable:
        return {"tuning_status": "skipped", "skip_reason": "all_candidate_fits_failed"}
    selectable.sort(
        key=lambda item: (
            float(item["objective"]),
            float(item.get("secondary_objective", -999.0)),
            float(item.get("tertiary_objective") or -999.0),
        ),
        reverse=True,
    )
    best = selectable[0]

    # Refit the selected candidate on the full train split before final validation.
    selected_model = next(model for params, model in candidates if params == best["params"])
    x_train, y_train = _xy(train_rows, feature_columns)
    x_val, y_val = _xy(validation_rows, feature_columns)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
        warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
        selected_model.fit(x_train, y_train)
    if is_classifier:
        val_scores = _positive_scores(selected_model, x_val)
        pre_preds = [1 if value >= 0.5 else 0 for value in val_scores]
        post_preds = [1 if value >= float(best["threshold"]) else 0 for value in val_scores]
        pre_metric = _classification_metric([int(value) for value in y_val], pre_preds)
        post_metric = _classification_metric([int(value) for value in y_val], post_preds)
        supports_probability = True
    else:
        val_preds = [float(value) for value in selected_model.predict(x_val)]
        pre_metric = _regression_metric([float(value) for value in y_val], val_preds)
        post_metric = pre_metric
        supports_probability = False
    return {
        "tuning_status": "completed",
        "selected_hyperparameters": best["params"],
        "selected_threshold": best["threshold"] if is_classifier else None,
        "pre_tune_validation_metrics": pre_metric,
        "post_tune_validation_metrics": post_metric,
        "supports_probability": supports_probability,
        "candidate_count": len(candidates),
        "candidate_fit_attempt_count": len(candidate_results),
        "candidate_search_stopped_early": search_stopped_early,
        "model_object": selected_model,
        "feature_columns": feature_columns,
    }


def _forecast_actual_rows_for_validation(
    *,
    spec: dict,
    validation_rows: list[dict],
    tuning: dict,
) -> list[dict]:
    model_key = str(spec["model_key"])
    target = str(spec["target"])
    model = tuning.get("model_object")
    feature_columns = tuning.get("feature_columns") or _feature_columns(validation_rows)
    rows: list[dict[str, Any]] = []
    if model_key == "previous_direction":
        probabilities = [float(pred) for pred in _previous_direction_predict(validation_rows)]
        predicted_returns = [None for _ in validation_rows]
    elif model_key in SUPPORTED_CLASSIFICATION_MODELS:
        x_val, _ = _xy(validation_rows, feature_columns)
        probabilities = _positive_scores(model, x_val)
        predicted_returns = [None for _ in validation_rows]
    else:
        x_val, _ = _xy(validation_rows, feature_columns)
        predictions = [float(value) for value in model.predict(x_val)]
        probabilities = [1.0 if value >= 0 else 0.0 for value in predictions]
        predicted_returns = predictions

    threshold = tuning.get("selected_threshold")
    threshold_value = 0.5 if threshold is None else float(threshold)
    for source, probability, predicted_return in zip(validation_rows, probabilities, predicted_returns):
        if target in {"forward_return", "volatility_adjusted_return"}:
            actual_return = (
                source.get("future_return")
                if target == "forward_return"
                else source.get("volatility_adjusted_future_return")
            )
            predicted_direction = "up" if (predicted_return or 0.0) >= 0 else "down"
            actual_direction = "up" if float(actual_return) > 0 else "down" if float(actual_return) < 0 else "flat"
        elif target == "market_relative_direction":
            actual_return = source.get("market_relative_return")
            predicted_direction = "up" if probability >= threshold_value else "down"
            actual_direction = source.get("market_relative_direction")
        else:
            actual_return = source.get("future_return")
            predicted_direction = "up" if probability >= threshold_value else "down"
            actual_direction = source.get("future_direction")
        rows.append(
            {
                "ticker": source["ticker"],
                "model_id": model_key,
                "model_family": spec["model_family"],
                "horizon": spec["horizon"],
                "forecast_timestamp": source["timestamp"],
                "target": target,
                "predicted_direction": predicted_direction,
                "actual_direction": actual_direction,
                "predicted_probability": probability,
                "predicted_return": predicted_return,
                "actual_return": actual_return,
                "selected_threshold": threshold,
            }
        )
    return rows


def train_one_model_spec(
    spec: dict,
    dataset_rows: list[dict],
    *,
    output_root: str,
    timeout_seconds_per_model: int | None = None,
) -> dict:
    """Train one eligible model group and append compact validation rows."""

    started = time.monotonic()
    rows = _rows_for_spec(spec, dataset_rows)
    if len(rows) < MIN_ROWS_PER_MODEL:
        return {
            "model_key": spec["model_key"],
            "target": spec["target"],
            "horizon": spec["horizon"],
            "training_status": "skipped",
            "skip_reason": "insufficient_rows_for_model_horizon_target",
            "available_rows": len(rows),
        }
    train_rows, validation_rows, split_diagnostics = _purged_or_temporal_split(rows, int(spec["horizon"]))
    if len(validation_rows) < MIN_VALIDATION_ROWS:
        return {
            "model_key": spec["model_key"],
            "target": spec["target"],
            "horizon": spec["horizon"],
            "training_status": "skipped",
            "skip_reason": "insufficient_validation_rows",
            "available_rows": len(rows),
        }
    tuning = tune_one_model_spec(
        spec,
        train_rows,
        validation_rows,
        timeout_seconds=timeout_seconds_per_model,
    )
    if tuning.get("tuning_status") != "completed":
        return {
            "model_key": spec["model_key"],
            "target": spec["target"],
            "horizon": spec["horizon"],
            "training_status": "skipped",
            "skip_reason": tuning.get("skip_reason", "tuning_failed"),
            "available_rows": len(rows),
        }
    validation_forecasts = _forecast_actual_rows_for_validation(
        spec=spec,
        validation_rows=validation_rows,
        tuning=tuning,
    )
    root = _output_root(output_root)
    forecast_path = root / "forecast_actual_rows.jsonl"
    with forecast_path.open("a", encoding="utf-8") as handle:
        for row in validation_forecasts:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    adapter = get_adapter(str(spec["model_key"]))
    evidence_record = {
        "record_id": f"generated_{spec['model_key']}_{spec['target']}_h{spec['horizon']}",
        "model_key": spec["model_key"],
        "model_family": spec["model_family"],
        "model_display_name": adapter.display_name,
        "target": spec["target"],
        "horizon": int(spec["horizon"]),
        "execution_mode": "local_full_model_run",
        "validation_rows": len(validation_rows),
        "train_rows": len(train_rows),
        "selected_hyperparameters": tuning.get("selected_hyperparameters"),
        "selected_threshold": tuning.get("selected_threshold"),
        "candidate_count": tuning.get("candidate_count"),
        "candidate_fit_attempt_count": tuning.get("candidate_fit_attempt_count"),
        "candidate_search_stopped_early": tuning.get("candidate_search_stopped_early"),
        "split_diagnostics": split_diagnostics,
        "pre_tune_validation_metrics": tuning.get("pre_tune_validation_metrics"),
        "post_tune_validation_metrics": tuning.get("post_tune_validation_metrics"),
        "claim_scope": "diagnostic_only",
    }
    if adapter.dependency_status in {"missing_dependency", "optional_dependency"}:
        evidence_record["execution_mode"] = "metadata_only_static_demo"
    elapsed = round(time.monotonic() - started, 6)
    return {
        "model_key": spec["model_key"],
        "model_family": spec["model_family"],
        "target": spec["target"],
        "horizon": spec["horizon"],
        "training_status": "completed",
        "tuning_status": "completed",
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "pre_tune_validation_metrics": tuning.get("pre_tune_validation_metrics"),
        "post_tune_validation_metrics": tuning.get("post_tune_validation_metrics"),
        "selected_hyperparameters": tuning.get("selected_hyperparameters"),
        "selected_threshold": tuning.get("selected_threshold"),
        "split_diagnostics": split_diagnostics,
        "forecast_rows_written": len(validation_forecasts),
        "evidence_record": evidence_record,
        "elapsed_seconds": elapsed,
        "timeout_exceeded": False,
    }


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"completed_keys": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _spec_key(spec: dict) -> str:
    return f"{spec['model_key']}|{spec['target']}|h{spec['horizon']}"


def run_full_eligible_model_training(
    *,
    dataset_path: str,
    output_root: str,
    max_models: int | None = None,
    max_workers: int = 1,
    timeout_seconds_per_model: int = 120,
) -> dict:
    """Run bounded local training for all eligible model groups."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    root = _output_root(output_root)
    forecast_path = root / "forecast_actual_rows.jsonl"
    if not forecast_path.exists():
        forecast_path.write_text("", encoding="utf-8")
    dataset_rows = _load_jsonl(dataset_path)
    discovered = discover_trainable_model_specs()
    specs = discovered["trainable_model_specs"]
    if max_models is not None:
        specs = specs[: int(max_models)]
    checkpoint_path = root / "training_checkpoint.json"
    checkpoint = _load_checkpoint(checkpoint_path)
    completed_keys = set(checkpoint.get("completed_keys", []))
    results: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    timed_out = 0
    for spec in specs:
        key = _spec_key(spec)
        if key in completed_keys:
            skipped.append({**spec, "training_status": "skipped", "skip_reason": "already_completed_checkpoint"})
            continue
        started = time.monotonic()
        result = train_one_model_spec(
            spec,
            dataset_rows,
            output_root=str(root),
            timeout_seconds_per_model=timeout_seconds_per_model,
        )
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds_per_model:
            result["timeout_exceeded"] = True
            timed_out += 1
        results.append(result)
        if result.get("training_status") == "completed":
            completed_keys.add(key)
            evidence_records.append(result["evidence_record"])
        else:
            skipped.append(result)
        _write_json(checkpoint_path, {"completed_keys": sorted(completed_keys), "last_key": key})
    _write_json(root / "model_evidence_records.json", {"records": evidence_records})
    tuned_models = [
        {
            "model_id": item.get("model_key"),
            "target": item.get("target"),
            "horizon": item.get("horizon"),
            "selected_threshold": item.get("selected_threshold"),
            "pre_tune_validation": item.get("pre_tune_validation_metrics"),
            "post_tune_validation": item.get("post_tune_validation_metrics"),
            "sample_count": item.get("train_rows", 0) + item.get("validation_rows", 0),
        }
        for item in results
        if item.get("training_status") == "completed"
    ]
    _write_json(
        root / "tuning_report.json",
        {
            "tuning_status": "completed" if tuned_models else "no_eligible_models",
            "eligible_model_count": len(tuned_models),
            "skipped_model_count": len(skipped),
            "tuned_models": tuned_models,
            "skipped_models": skipped,
            "training_ran": True,
            "tuning_ran": bool(tuned_models),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        },
    )
    training_summary = {
        "training_run_status": "completed" if evidence_records else "completed_no_trainable_data",
        "dataset_path": dataset_path,
        "dataset_row_count": len(dataset_rows),
        "attempted_model_specs": len(specs),
        "trained_model_specs": len(evidence_records),
        "tuned_model_specs": len(evidence_records),
        "skipped_model_specs": len(skipped),
        "timed_out_model_specs": timed_out,
        "max_workers_requested": max_workers,
        "max_workers_used": 1,
        "timeout_seconds_per_model": timeout_seconds_per_model,
        "forecast_actual_output": str(forecast_path),
        "evidence_record_output": str(root / "model_evidence_records.json"),
        "tuning_report_output": str(root / "tuning_report.json"),
        "model_results": [{key: value for key, value in item.items() if key != "evidence_record"} for item in results],
        "skipped_models": skipped,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "training_run_summary.json", training_summary)
    return training_summary


def render_full_eligible_model_training_report(result: dict) -> str:
    """Render a compact training report."""

    skip_counter = Counter(item.get("skip_reason", "none") for item in result.get("skipped_models", []))
    lines = [
        "# Full Eligible Model Training",
        "",
        f"Training run status: {result.get('training_run_status')}",
        f"Dataset rows: {result.get('dataset_row_count')}",
        f"Attempted model specs: {result.get('attempted_model_specs')}",
        f"Trained model specs: {result.get('trained_model_specs')}",
        f"Tuned model specs: {result.get('tuned_model_specs')}",
        f"Skipped model specs: {result.get('skipped_model_specs')}",
        f"Timed out model specs: {result.get('timed_out_model_specs')}",
        "",
        "Top skip reasons:",
        *([f"- {key}: {value}" for key, value in skip_counter.most_common(8)] or ["- none"]),
        "",
        "Boundary:",
        "Models are trained only from local supervised rows and no model binaries are written.",
        "Validation metrics are temporal-split diagnostics and require human review.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train all eligible local model groups.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-models", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--timeout-seconds-per-model", type=int, default=120)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_full_eligible_model_training(
        dataset_path=args.dataset,
        output_root=args.output_root,
        max_models=args.max_models,
        max_workers=args.max_workers,
        timeout_seconds_per_model=args.timeout_seconds_per_model,
    )
    if args.format == "report":
        print(render_full_eligible_model_training_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
