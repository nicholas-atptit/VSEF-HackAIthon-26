"""Release accuracy and tuning readiness report for local forecast-vs-actual evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_actual_artifact_discovery import discover_forecast_actual_artifacts
from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
)
from src.hackaithon_mvp.eligible_model_policy_tuner import tune_all_eligible_models
from src.hackaithon_mvp.forecast_60pct_release_gate import evaluate_60pct_release_gate
from src.hackaithon_mvp.release_model_tuning_gate import run_release_model_tuning_gate


MIN_RELEASE_DIRECTIONAL_ROWS = 30
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
NON_CLAIM_TEXT = "Release accuracy report is local-evidence only and requires human review."
MAX_DISCOVERED_EVALUATION_FILES = 5


def _load_tuning_output(path: str | None) -> dict | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else None


def _load_discovered_rows(discovery: dict) -> tuple[list[dict], list[str], list[str]]:
    rows: list[dict] = []
    input_paths: list[str] = []
    errors: list[str] = []
    for candidate in discovery.get("candidate_files", []):
        if not candidate.get("usable_for_accuracy"):
            continue
        if len(input_paths) >= MAX_DISCOVERED_EVALUATION_FILES:
            errors.append("discovered_evaluation_file_limit_reached")
            break
        path = str(candidate.get("path") or "")
        if not path:
            continue
        try:
            loaded = load_forecast_accuracy_rows(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{path}:{type(exc).__name__}")
            continue
        rows.extend(loaded)
        input_paths.append(path)
    return rows, input_paths, errors


def _release_status(accuracy: dict, tuning_gate: dict, tuning_result: dict | None) -> str:
    if accuracy.get("accuracy_status") == "not_ready_no_forecast_actual_rows":
        return "not_ready_no_forecast_actual_rows"
    directional = (accuracy.get("global") or {}).get("directional", {})
    coverage_count = int(directional.get("coverage_count") or 0)
    if coverage_count <= 0:
        return "not_ready_no_forecast_actual_rows"
    if coverage_count < MIN_RELEASE_DIRECTIONAL_ROWS:
        return "ready_for_demo_accuracy_disclosure"
    gate_status = tuning_gate.get("tuning_gate_status")
    if gate_status in {"ready_for_policy_threshold_tuning", "ready_for_model_hyperparameter_tuning"} and not tuning_result:
        return "not_ready_tuning_required"
    if tuning_result and tuning_result.get("tuning_status") == "completed":
        return "release_ready_with_local_accuracy"
    if gate_status in {"ready_for_release_evaluation_only", "not_ready_insufficient_rows"}:
        return "release_ready_with_local_accuracy"
    return "not_ready_insufficient_coverage"


def build_release_accuracy_report(
    *,
    input_path: str | None = None,
    discover: bool = False,
    tuning_output_path: str | None = None,
) -> dict:
    """Build a release accuracy report from explicit local rows or a discovery dry run."""

    if input_path and discover:
        raise ValueError("input_path and discover are mutually exclusive")
    discovery = discover_forecast_actual_artifacts(repo_root=".") if discover else None
    if input_path:
        rows = load_forecast_accuracy_rows(input_path)
        accuracy = evaluate_forecast_accuracy(rows)
        tuning_gate = run_release_model_tuning_gate(rows)
        discovered_inputs: list[str] = []
        discovery_errors: list[str] = []
    elif discover and discovery is not None:
        rows, discovered_inputs, discovery_errors = _load_discovered_rows(discovery)
        accuracy = evaluate_forecast_accuracy(rows)
        tuning_gate = run_release_model_tuning_gate(rows)
    else:
        rows = []
        discovered_inputs = []
        discovery_errors = []
        accuracy = evaluate_forecast_accuracy(rows)
        tuning_gate = run_release_model_tuning_gate(rows)
    tuning_result = _load_tuning_output(tuning_output_path)
    if (
        tuning_result is None
        and discover
        and tuning_gate.get("tuning_gate_status") == "ready_for_policy_threshold_tuning"
    ):
        tuning_result = tune_all_eligible_models(rows)
    status = _release_status(accuracy, tuning_gate, tuning_result)
    directional = (accuracy.get("global") or {}).get("directional", {})
    forecast_60pct_gate = evaluate_60pct_release_gate(
        {
            "accuracy_evaluation": accuracy,
            "evaluated_row_count": accuracy.get("evaluated_row_count", 0),
            "final_holdout_accuracy": directional.get("accuracy"),
            "final_holdout_balanced_accuracy": directional.get("balanced_accuracy"),
            "final_holdout_mcc": directional.get("mcc"),
            "final_holdout_rows": directional.get("coverage_count"),
            "final_holdout_coverage": 1.0 if directional.get("coverage_count") else 0.0,
            "baseline_comparison": accuracy.get("baseline_comparison"),
        }
    )
    limitations = []
    if not input_path:
        limitations.append("explicit_input_required_for_accuracy")
    if discovered_inputs:
        limitations = [item for item in limitations if item != "explicit_input_required_for_accuracy"]
    if discovery_errors:
        limitations.append("some_discovered_inputs_failed_to_load")
    if status == "ready_for_demo_accuracy_disclosure":
        limitations.append("directional_coverage_below_release_threshold")
    if tuning_gate.get("tuning_gate_status") == "ready_for_policy_threshold_tuning" and not tuning_result:
        limitations.append("eligible_threshold_tuning_not_run")
    if tuning_gate.get("tuning_gate_status") == "not_ready_no_labeled_data":
        limitations.append("local_labeled_rows_missing")
    return {
        "release_accuracy_status": status,
        "artifact_discovery": discovery,
        "input_path": input_path,
        "discovered_input_paths": discovered_inputs,
        "discovery_load_errors": discovery_errors,
        "evaluated_row_count": accuracy.get("evaluated_row_count", 0),
        "global_directional_accuracy": directional.get("accuracy"),
        "global_balanced_accuracy": directional.get("balanced_accuracy"),
        "forecast_release_status": forecast_60pct_gate.get("forecast_release_status"),
        "forecast_60pct_release_gate": forecast_60pct_gate,
        "forecast_release_allowed": forecast_60pct_gate.get("forecast_release_allowed"),
        "forecast_broad_performance_claim_allowed": forecast_60pct_gate.get("broad_performance_claim_allowed"),
        "confusion_matrix": directional.get("confusion_matrix"),
        "numeric_metrics": (accuracy.get("global") or {}).get("numeric"),
        "probability_metrics": (accuracy.get("global") or {}).get("probability"),
        "by_ticker": (accuracy.get("groups") or {}).get("by_ticker", {}),
        "by_horizon": (accuracy.get("groups") or {}).get("by_horizon", {}),
        "by_model_family": (accuracy.get("groups") or {}).get("by_model_family", {}),
        "by_model": (accuracy.get("groups") or {}).get("by_model_id", {}),
        "baseline_comparison": accuracy.get("baseline_comparison"),
        "accuracy_evaluation": accuracy,
        "tuning_readiness": tuning_gate,
        "tuning_result": tuning_result,
        "release_gate": {
            "status": status,
            "forecast_release_status": forecast_60pct_gate.get("forecast_release_status"),
            "hard_60pct_gate_passed": forecast_60pct_gate.get("forecast_release_allowed"),
            "min_release_directional_rows": MIN_RELEASE_DIRECTIONAL_ROWS,
            "human_review_required": True,
        },
        "limitations": sorted(set(limitations)),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _fmt(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def _compact_group_lines(groups: dict[str, dict]) -> list[str]:
    if not groups:
        return ["- none"]
    lines = []
    for key, value in list(groups.items())[:10]:
        directional = (value.get("directional") or {})
        lines.append(
            f"- {key}: rows={directional.get('sample_count')}, "
            f"coverage={directional.get('coverage_count')}, "
            f"accuracy={_fmt(directional.get('accuracy'))}, "
            f"balanced_accuracy={_fmt(directional.get('balanced_accuracy'))}"
        )
    if len(groups) > 10:
        lines.append(f"- additional groups omitted from report: {len(groups) - 10}")
    return lines


def render_release_accuracy_report(result: dict) -> str:
    """Render a compact release accuracy report."""

    baseline = result.get("baseline_comparison") or {}
    tuning = result.get("tuning_readiness") or {}
    tuning_result = result.get("tuning_result") or {}
    release_gate = result.get("release_gate") or {}
    forecast_gate = result.get("forecast_60pct_release_gate") or {}
    tuned_lines = []
    for item in tuning_result.get("tuned_models", []) if isinstance(tuning_result, dict) else []:
        tuned_lines.append(
            "- {model_id}/h{horizon}: threshold={threshold}, pre_bacc={pre}, post_bacc={post}".format(
                model_id=item.get("model_id"),
                horizon=item.get("horizon"),
                threshold=item.get("selected_threshold"),
                pre=(item.get("pre_tune_validation") or {}).get("balanced_accuracy"),
                post=(item.get("post_tune_validation") or {}).get("balanced_accuracy"),
            )
        )
    if not tuned_lines:
        tuned_lines = ["- none"]
    lines = [
        "# Release Accuracy Report",
        "",
        f"Release accuracy status: {result.get('release_accuracy_status')}",
        f"Evaluated rows: {result.get('evaluated_row_count')}",
        f"Discovered inputs evaluated: {len(result.get('discovered_input_paths') or [])}",
        f"Global directional accuracy: {_fmt(result.get('global_directional_accuracy'))}",
        f"Global balanced accuracy: {_fmt(result.get('global_balanced_accuracy'))}",
        f"Confusion matrix: {result.get('confusion_matrix')}",
        "",
        "Baseline comparison:",
        f"- majority class: {_fmt(baseline.get('majority_class_baseline_accuracy'))}",
        f"- random 50/50: {_fmt(baseline.get('random_50_50_baseline_accuracy'))}",
        f"- previous direction: {_fmt(baseline.get('previous_direction_baseline_accuracy'))}",
        f"- zero-return MAE: {_fmt((baseline.get('naive_zero_return_baseline') or {}).get('mae'))}",
        "",
        "By ticker:",
        *_compact_group_lines(result.get("by_ticker") or {}),
        "",
        "By horizon:",
        *_compact_group_lines(result.get("by_horizon") or {}),
        "",
        "By model family:",
        *_compact_group_lines(result.get("by_model_family") or {}),
        "",
        "By model:",
        *_compact_group_lines(result.get("by_model") or {}),
        "",
        f"Tuning readiness: {tuning.get('tuning_gate_status')}",
        f"Tuning result included: {result.get('tuning_result') is not None}",
        "Tuning validation summary:",
        *tuned_lines,
        f"Release gate status: {release_gate.get('status')}",
        f"60 percent forecast release status: {forecast_gate.get('forecast_release_status')}",
        f"60 percent forecast release allowed: {forecast_gate.get('forecast_release_allowed')}",
        "",
        "Limitations:",
        *[f"- {item}" for item in (result.get("limitations") or ["none"])],
        "",
        "Boundary:",
        "Accuracy requires local labeled forecast-vs-actual rows; missing evidence is skipped, not fabricated.",
        "No external data access, model update, or market-action output is performed.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local release accuracy report.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--tuning-output", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        result = build_release_accuracy_report(
            input_path=args.input,
            discover=args.discover,
            tuning_output_path=args.tuning_output,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.format == "report":
        print(render_release_accuracy_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
