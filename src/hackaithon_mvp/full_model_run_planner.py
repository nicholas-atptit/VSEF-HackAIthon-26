"""Plan a bounded local full-model run from available repo artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_catalog.stack_catalog_generator import generate_stack_catalog
from src.hackaithon_mvp.engine_catalog.support_catalog_generator import generate_support_catalog
from src.hackaithon_mvp.forecast_actual_artifact_discovery import discover_forecast_actual_artifacts
from src.hackaithon_mvp.local_training_dataset_builder import discover_local_ohlcv_sources


SUPPORTED_CLASSIFICATION_MODELS = {
    "majority_class",
    "previous_direction",
    "logistic_l1",
    "logistic_l2",
    "ridge_classifier",
    "random_forest",
    "sklearn_gradient_boosting",
    "hist_gradient_boosting",
}
SUPPORTED_REGRESSION_MODELS = {"linear_regression", "ridge_regression", "random_forest_regressor"}
SUPPORTED_MODEL_KEYS = SUPPORTED_CLASSIFICATION_MODELS | SUPPORTED_REGRESSION_MODELS
SUPPORTED_DIRECTION_TARGETS = {"absolute_direction", "return_direction", "market_relative_direction"}
SUPPORTED_RETURN_TARGETS = {"forward_return", "volatility_adjusted_return"}
CLAIM_BOUNDARY = {
    "local_planning_only": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Full-run planner only; execution requires explicit .tmp_full_model_run output."


def _is_trainable_baseline_spec(spec) -> tuple[bool, str | None]:
    if spec.model_key not in SUPPORTED_MODEL_KEYS:
        return False, "model_wrapper_not_supported"
    if spec.model_key in SUPPORTED_CLASSIFICATION_MODELS and spec.target not in SUPPORTED_DIRECTION_TARGETS:
        return False, "target_not_supported_by_classifier"
    if spec.model_key in SUPPORTED_REGRESSION_MODELS and spec.target not in SUPPORTED_RETURN_TARGETS:
        return False, "target_not_supported_by_regressor"
    return True, None


def inspect_available_training_inputs(*, repo_root: str = ".") -> dict:
    """Inspect local data and artifact inputs needed for a full local run."""

    ohlcv = discover_local_ohlcv_sources(repo_root=repo_root)
    forecast_actual = discover_forecast_actual_artifacts(repo_root=repo_root)
    baseline_specs = generate_baseline_catalog()
    support_specs = generate_support_catalog()
    stack_specs = generate_stack_catalog()
    families = Counter(spec.model_family for spec in baseline_specs)
    horizons = Counter(str(spec.horizon) for spec in baseline_specs)
    feature_sets = Counter(spec.feature_set for spec in baseline_specs)
    targets = Counter(spec.target for spec in baseline_specs)
    return {
        "inspection_status": "completed",
        "ohlcv_source_count": ohlcv["candidate_file_count"],
        "preferred_ohlcv_source_count": ohlcv["preferred_file_count"],
        "ticker_count_estimate": ohlcv["ticker_count_estimate"],
        "forecast_actual_candidate_count": forecast_actual["candidate_file_count"],
        "usable_forecast_actual_count": forecast_actual["usable_accuracy_file_count"],
        "baseline_spec_count": len(baseline_specs),
        "auxiliary_spec_count": len(support_specs),
        "stack_spec_count": len(stack_specs),
        "model_family_distribution": dict(sorted(families.items())),
        "horizon_distribution": dict(sorted(horizons.items())),
        "feature_set_distribution": dict(sorted(feature_sets.items())),
        "target_distribution": dict(sorted(targets.items())),
        "ohlcv_discovery": ohlcv,
        "forecast_actual_discovery": forecast_actual,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def build_full_model_run_plan(*, repo_root: str = ".", max_tickers: int | None = None) -> dict:
    """Build a no-write full-run plan from local input availability and engine specs."""

    inspection = inspect_available_training_inputs(repo_root=repo_root)
    runnable_baseline = []
    blocked_counter: Counter[str] = Counter()
    grouped_seen: set[tuple[str, str, int]] = set()
    for spec in generate_baseline_catalog():
        trainable, reason = _is_trainable_baseline_spec(spec)
        if not trainable:
            blocked_counter[str(reason)] += 1
            continue
        key = (str(spec.model_key), str(spec.target), int(spec.horizon))
        if key in grouped_seen:
            continue
        grouped_seen.add(key)
        runnable_baseline.append(
            {
                "model_key": spec.model_key,
                "model_family": spec.model_family,
                "target": spec.target,
                "horizon": spec.horizon,
                "representative_engine_id": spec.engine_id,
            }
        )
    if inspection["ohlcv_source_count"] == 0:
        blocked_counter["local_ohlcv_sources_missing"] += len(runnable_baseline)
        runnable_baseline = []
    if max_tickers == 0:
        blocked_counter["max_tickers_zero"] += len(runnable_baseline)
        runnable_baseline = []

    family_target_horizon = {
        (item["model_family"], item["target"], item["horizon"])
        for item in runnable_baseline
    }
    runnable_auxiliary = []
    for spec in generate_support_catalog():
        if (spec.model_family, spec.target, spec.horizon) in family_target_horizon:
            runnable_auxiliary.append(
                {
                    "engine_id": spec.engine_id,
                    "model_family": spec.model_family,
                    "target": spec.target,
                    "horizon": spec.horizon,
                    "dependency": spec.dependencies[0] if spec.dependencies else None,
                }
            )
        else:
            blocked_counter["required_baseline_family_outputs_unavailable"] += 1

    classification_targets = {item["target"] for item in runnable_baseline if item["model_family"] == "classification"}
    runnable_stack = []
    for spec in generate_stack_catalog():
        if spec.target in classification_targets and spec.horizon in {item["horizon"] for item in runnable_baseline}:
            runnable_stack.append(
                {
                    "engine_id": spec.engine_id,
                    "target": spec.target,
                    "horizon": spec.horizon,
                    "dependency": spec.dependencies[0] if spec.dependencies else None,
                }
            )
        else:
            blocked_counter["required_support_outputs_unavailable"] += 1

    runtime_class = "small" if len(runnable_baseline) <= 25 else "medium" if len(runnable_baseline) <= 150 else "large"
    return {
        "plan_status": "ready" if runnable_baseline else "blocked_by_data_unavailability",
        "inspection": inspection,
        "max_tickers": max_tickers,
        "runnable_baseline_specs": runnable_baseline,
        "runnable_threshold_tuning_specs": [
            item for item in runnable_baseline if item["model_key"] in SUPPORTED_CLASSIFICATION_MODELS
        ],
        "runnable_hyperparameter_tuning_specs": runnable_baseline,
        "runnable_auxiliary_specs": runnable_auxiliary,
        "runnable_stack_specs": runnable_stack,
        "blocked_specs_by_reason": dict(sorted(blocked_counter.items())),
        "required_data_to_unblock": [
            "local OHLCV bars by ticker and timestamp",
            "future local bars for each target horizon",
            "feature matrix columns derived without future leakage",
            "dependency outputs for auxiliary and stack specs",
        ],
        "estimated_runtime_class": runtime_class,
        "safe_execution_plan": [
            "write generated outputs only under .tmp_full_model_run",
            "use temporal train/validation split",
            "checkpoint after each model group",
            "materialize compact static evidence and dependency outputs",
            "rerun generated engine universe with generated evidence",
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_full_model_run_plan_report(result: dict) -> str:
    """Render a compact full-run plan report."""

    lines = [
        "# Full Local Model Run Plan",
        "",
        f"Plan status: {result.get('plan_status')}",
        f"Runnable baseline model groups: {len(result.get('runnable_baseline_specs') or [])}",
        f"Runnable threshold tuning groups: {len(result.get('runnable_threshold_tuning_specs') or [])}",
        f"Runnable hyperparameter tuning groups: {len(result.get('runnable_hyperparameter_tuning_specs') or [])}",
        f"Runnable auxiliary specs: {len(result.get('runnable_auxiliary_specs') or [])}",
        f"Runnable stack specs: {len(result.get('runnable_stack_specs') or [])}",
        f"Estimated runtime class: {result.get('estimated_runtime_class')}",
        "",
        "Blocked specs by reason:",
    ]
    blocked = result.get("blocked_specs_by_reason") or {}
    lines.extend([f"- {key}: {value}" for key, value in blocked.items()] or ["- none"])
    lines.extend(
        [
            "",
            "Safe execution plan:",
            *[f"- {item}" for item in result.get("safe_execution_plan", [])],
            "",
            "Boundary:",
            "Planner does not train, fetch data, or write files.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a safe local full-model run.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_full_model_run_plan(repo_root=args.repo_root, max_tickers=args.max_tickers)
    if args.format == "report":
        print(render_full_model_run_plan_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
