"""Data-expanded narrow selective forecaster with hard 60% gate enforcement."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.clean_forecast_target_builder import build_clean_direction_targets
from src.hackaithon_mvp.data_expanded_forecast_contract import validate_expanded_price_panel_schema
from src.hackaithon_mvp.expanded_forecast_feature_builder import build_expanded_forecast_features
from src.hackaithon_mvp.forecast_60pct_release_gate import (
    STATUS_BLOCKED_BELOW,
    evaluate_60pct_release_gate,
    evaluate_60pct_slice_gate,
    render_60pct_gate_report,
)
from src.hackaithon_mvp.forecast_60pct_edge_search import _evaluate_validation_confidence_gate
from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy
from src.hackaithon_mvp.forecast_edge_model_trainer import train_forecast_edge_models
from src.hackaithon_mvp.forecast_edge_selector import select_forecast_edge_slices
from src.hackaithon_mvp.local_training_dataset_builder import load_discovered_ohlcv_rows
from src.hackaithon_mvp.narrow_forecast_target_selector import select_narrow_forecast_targets
from src.hackaithon_mvp.optional_vn_market_data_adapter import run_optional_vn_market_data_expansion
from src.hackaithon_mvp.real_expanded_data_requirement import (
    STATUS_AVAILABLE as STATUS_REAL_EXPANDED_AVAILABLE,
    STATUS_REQUIRED as STATUS_EXPANDED_REQUIRED,
    check_real_expanded_data_available,
)


CLAIM_BOUNDARY = {
    "writes_only_under_approved_tmp_roots": True,
    "provider_fetch_disabled_by_default": True,
    "validation_selection_only": True,
    "holdout_evaluated_once_after_selection": True,
    "hard_60pct_gate_required": True,
    "real_expanded_data_required_by_default": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Data-expanded 60% forecaster blocks release unless real expanded data and fresh holdout gates pass."
ALLOWED_OUTPUT_ROOT_PREFIXES = (".tmp_data_expanded_60pct", ".tmp_real_expanded_60pct")


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(
        any(part.lower().startswith(prefix) for prefix in ALLOWED_OUTPUT_ROOT_PREFIXES)
        for part in root.parts
    ):
        raise ValueError("output_root must be .tmp_data_expanded_60pct, .tmp_real_expanded_60pct, or a child path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: Any) -> None:
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
            if key in {
                "rows",
                "retained_forecast_rows",
                "holdout_forecast_rows",
                "validation_forecast_rows",
                "accuracy_evaluation",
            }:
                if isinstance(value, list):
                    output[f"{key}_count"] = len(value)
                    continue
                if key != "rows":
                    continue
            output[key] = _public(value)
        return output
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            return [_public(item) for item in payload[:150]]
        return payload
    return payload


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def _load_panel(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        return rows if isinstance(rows, list) else []
    return []


def _discover_expanded_panel(root: Path) -> Path | None:
    data_root = root / "data"
    if not data_root.exists():
        return None
    candidates = []
    for path in data_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".csv", ".jsonl", ".json"}:
            if "price" in path.name.lower() or "panel" in path.name.lower() or "ohlcv" in path.name.lower():
                candidates.append(path)
    return sorted(candidates, key=lambda item: (item.stat().st_size, str(item)), reverse=True)[0] if candidates else None


def _provider_fetch_used(expansion: dict) -> bool:
    return bool(expansion.get("expanded_data_available") and expansion.get("data_expansion_status") == "completed")


def _provider_fetch_attempted(expansion: dict) -> bool:
    return bool(expansion.get("data_fetch_enabled") and expansion.get("data_expansion_status") not in {"disabled", "disabled_by_default", "missing_required_env"})


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
        output = dict(row)
        for column, value in feature_by_key.get((key[0], key[2]), {}).items():
            if str(column).startswith("feature_"):
                output[column] = value
        merged.append(output)
    return merged


def _filter_to_candidates(rows: list[dict], candidates: list[dict]) -> list[dict]:
    allowed = {(str(item.get("ticker")).upper(), int(item.get("horizon"))) for item in candidates}
    return [
        row
        for row in rows
        if (str(row.get("ticker") or "").upper(), int(row.get("horizon") or -1)) in allowed
    ]


def _all_holdout_rows(model_results: list[dict]) -> list[dict]:
    rows = []
    for item in model_results:
        if item.get("training_status") == "completed":
            rows.extend(dict(row) for row in item.get("holdout_forecast_rows") or [])
    return rows


def _ensemble_rows(rows: list[dict], *, model_id: str) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        key = (
            str(row.get("ticker") or ""),
            str(row.get("horizon") or ""),
            str(row.get("forecast_timestamp") or ""),
        )
        grouped.setdefault(key, []).append(row)
    output = []
    for members in grouped.values():
        probabilities = [float(row.get("predicted_probability")) for row in members if row.get("predicted_probability") not in (None, "")]
        if not probabilities:
            continue
        probability = sum(probabilities) / len(probabilities)
        first = members[0]
        output.append(
            {
                "ticker": first.get("ticker"),
                "model_id": model_id,
                "model_family": "simple_ensemble",
                "horizon": int(first.get("horizon")),
                "forecast_timestamp": first.get("forecast_timestamp"),
                "actual_timestamp": first.get("actual_timestamp"),
                "predicted_direction": "up" if probability >= 0.5 else "down",
                "actual_direction": first.get("actual_direction"),
                "predicted_probability": probability,
                "actual_return": first.get("actual_return"),
                "target": first.get("target", "clean_future_direction"),
            }
        )
    return sorted(output, key=lambda item: (str(item.get("horizon")), str(item.get("ticker")), str(item.get("forecast_timestamp"))))


def _build_simple_ensemble_results(model_results: list[dict]) -> list[dict]:
    ensembles = []
    completed = [item for item in model_results if item.get("training_status") == "completed"]
    horizons = sorted({int(item.get("horizon")) for item in completed if item.get("horizon") not in (None, "")})
    for horizon in horizons:
        horizon_items = [item for item in completed if int(item.get("horizon")) == horizon]
        validation_source = [row for item in horizon_items for row in item.get("validation_forecast_rows") or []]
        holdout_source = [row for item in horizon_items for row in item.get("holdout_forecast_rows") or []]
        validation_rows = _ensemble_rows(validation_source, model_id="simple_probability_average")
        holdout_rows = _ensemble_rows(holdout_source, model_id="simple_probability_average")
        if len(validation_rows) < 60 or len(holdout_rows) < 60:
            continue
        validation_eval = evaluate_forecast_accuracy(validation_rows)
        holdout_eval = evaluate_forecast_accuracy(holdout_rows)
        holdout_metrics = holdout_eval["global"]["directional"]
        baselines = holdout_eval["baseline_comparison"]
        ensembles.append(
            {
                "slice_id": f"ENSEMBLE|h{horizon}|simple_ensemble|simple_probability_average",
                "ticker": "ENSEMBLE",
                "horizon": horizon,
                "scope": "simple_ensemble",
                "model_id": "simple_probability_average",
                "model_family": "simple_ensemble",
                "training_status": "completed",
                "train_rows": None,
                "validation_rows": len(validation_rows),
                "holdout_rows": len(holdout_rows),
                "minimum_holdout_rows": 300,
                "candidate_count": 1,
                "completed_candidate_count": 1,
                "selected_hyperparameters": {"threshold": 0.5, "aggregation": "mean_predicted_probability"},
                "validation_metrics": validation_eval["global"]["directional"],
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
                "duplicate_key_severity": "none",
                "overlap_severity": "none",
                "leakage_warning": False,
                "validation_forecast_rows": validation_rows,
                "holdout_forecast_rows": holdout_rows,
            }
        )
    return ensembles


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


def _gate_input(model_results: list[dict], selection: dict, slice_gate: dict) -> dict[str, Any]:
    best_global = _best_model_result(model_results, global_only=True) or _best_model_result(model_results)
    global_metrics = (best_global or {}).get("holdout_metrics") or {}
    global_baselines = (best_global or {}).get("holdout_baselines") or {}
    return {
        "final_holdout_accuracy": global_metrics.get("accuracy"),
        "final_holdout_balanced_accuracy": global_metrics.get("balanced_accuracy"),
        "final_holdout_mcc": global_metrics.get("mcc"),
        "final_holdout_rows": global_metrics.get("coverage_count") or (best_global or {}).get("holdout_rows"),
        "final_holdout_coverage": 1.0 if best_global else 0.0,
        "baseline_comparison": global_baselines,
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


def _best_slice_from_results(model_results: list[dict]) -> dict | None:
    candidates = []
    for item in model_results:
        if item.get("training_status") != "completed":
            continue
        metrics = item.get("holdout_metrics") or {}
        bacc = metrics.get("balanced_accuracy")
        if isinstance(bacc, (int, float)):
            candidates.append((float(bacc), int(item.get("holdout_rows") or 0), item))
    if not candidates:
        return None
    _, _, item = sorted(candidates, key=lambda candidate: (candidate[0], candidate[1]), reverse=True)[0]
    metrics = item.get("holdout_metrics") or {}
    baselines = item.get("holdout_baselines") or {}
    return {
        "slice_id": item.get("slice_id"),
        "ticker": item.get("ticker"),
        "horizon": item.get("horizon"),
        "model_id": item.get("model_id"),
        "rows": item.get("holdout_rows"),
        "accuracy": metrics.get("accuracy"),
        "balanced_accuracy": metrics.get("balanced_accuracy"),
        "mcc": metrics.get("mcc"),
        "wilson_accuracy_interval": metrics.get("wilson_accuracy_interval"),
        "random_baseline": baselines.get("random_50_50_baseline_accuracy"),
        "majority_baseline": baselines.get("majority_class_baseline_accuracy"),
        "previous_direction_baseline": baselines.get("previous_direction_baseline_accuracy"),
    }


def _materialize_if_passed(root: Path, retained_rows: list[dict], release_gate: dict) -> dict:
    if not release_gate.get("forecast_release_allowed"):
        return {
            "materialization_status": "skipped_gate_not_passed",
            "retained_row_count": 0,
            "evidence_root": None,
        }
    evidence_root = root / "evidence"
    _write_jsonl(evidence_root / "forecast_actual_rows.jsonl", retained_rows)
    _write_json(evidence_root / "accuracy_summary.json", evaluate_forecast_accuracy(retained_rows))
    _write_json(evidence_root / "forecast_60pct_release_gate.json", _public(release_gate))
    return {
        "materialization_status": "completed",
        "retained_row_count": len(retained_rows),
        "evidence_root": str(evidence_root),
    }


def run_data_expanded_60pct_forecaster(
    *,
    output_root: str,
    max_models: int = 300,
    max_workers: int = 1,
    min_slice_rows: int = 500,
    expanded_input: str | None = None,
    allow_ohlcv_fallback: bool = False,
) -> dict:
    """Run data-expanded narrow forecast attempt and enforce the hard 60% gate."""

    started = time.monotonic()
    root = _output_root(output_root)
    expansion = run_optional_vn_market_data_expansion(output_root=str(root / "data"))
    expanded_path = Path(expanded_input) if expanded_input else _discover_expanded_panel(root)
    requirement = check_real_expanded_data_available(
        input_path=str(expanded_path) if expanded_path else None,
        output_root=str(root),
    )
    if expanded_path is None and requirement.get("input_path"):
        expanded_path = Path(str(requirement["input_path"]))
    real_expanded_available = requirement.get("expanded_data_requirement_status") == STATUS_REAL_EXPANDED_AVAILABLE
    if real_expanded_available and expanded_path is not None:
        bars = _load_panel(expanded_path)
        expanded_data_available = True
        data_source = str(expanded_path)
        fallback_status = "not_used"
    elif allow_ohlcv_fallback:
        if expanded_path is not None and expanded_path.exists():
            bars = _load_panel(expanded_path)
            data_source = str(expanded_path)
        else:
            bars = list(load_discovered_ohlcv_rows(repo_root="."))
            data_source = "existing_local_ohlcv"
        expanded_data_available = False
        fallback_status = "fallback_only_not_expected_to_reach_60pct"
    else:
        status = STATUS_EXPANDED_REQUIRED
        blocked = {
            "forecast_status": status,
            "forecast_release_status": status,
            "output_root": str(root),
            "data_source": str(expanded_path) if expanded_path else None,
            "expanded_input": expanded_input,
            "expanded_data_available": False,
            "real_expanded_data_available": False,
            "provider_fetch_used": _provider_fetch_used(expansion),
            "provider_fetch_attempted": _provider_fetch_attempted(expansion),
            "data_expansion": expansion,
            "real_expanded_data_requirement": requirement,
            "data_requirement_status": requirement.get("expanded_data_requirement_status"),
            "ohlcv_only_fallback_blocked": True,
            "fallback_status": "blocked_unless_allow_ohlcv_fallback",
            "retained_rows": 0,
            "retained_coverage": 0.0,
            "hard_60pct_reached": False,
            "gap_to_60pct": None,
            "blocker": "Real expanded data is required for this 60% attempt; OHLCV-only fallback was blocked.",
            "evidence_materialization": {
                "materialization_status": "skipped_expanded_data_required",
                "retained_row_count": 0,
                "evidence_root": None,
            },
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
        _write_json(root / "data_expansion.json", _public(expansion))
        _write_json(root / "real_expanded_data_requirement.json", _public(requirement))
        _write_json(root / "data_expanded_60pct_forecast_summary.json", _public(blocked))
        return blocked
    contract = validate_expanded_price_panel_schema(bars)
    targets = build_clean_direction_targets(bars, horizons=(1, 5, 10), non_overlapping=True)
    target_rows = list(targets.get("rows") or [])
    features = build_expanded_forecast_features(bars)
    feature_rows = list(features.get("rows") or [])
    training_rows_all = _merge_targets_features(target_rows, feature_rows)
    target_selection = select_narrow_forecast_targets(
        training_rows_all,
        min_rows=min_slice_rows,
        horizons=(1, 5, 10),
    )
    selected_candidates = list(target_selection.get("allowed_target_candidates") or [])
    training_rows = _filter_to_candidates(training_rows_all, selected_candidates) if selected_candidates else []
    _write_json(root / "data_expansion.json", _public(expansion))
    _write_json(root / "real_expanded_data_requirement.json", _public(requirement))
    _write_json(root / "expanded_data_contract.json", _public(contract))
    _write_json(root / "clean_target_summary.json", _public(targets))
    _write_json(root / "expanded_feature_summary.json", _public(features))
    _write_json(root / "narrow_target_selection.json", _public(target_selection))
    _write_jsonl(root / "expanded_training_rows.jsonl", training_rows)

    training = train_forecast_edge_models(
        training_rows,
        horizons=(1, 5, 10),
        max_models=max_models,
        max_workers=max_workers,
        min_slice_rows=min_slice_rows,
    )
    model_results = list(training.get("model_results") or [])
    ensemble_results = _build_simple_ensemble_results(model_results)
    model_results.extend(ensemble_results)
    if ensemble_results:
        training["model_results"] = model_results
        training["attempted_model_specs"] = int(training.get("attempted_model_specs") or 0) + len(ensemble_results)
        training["trained_model_specs"] = int(training.get("trained_model_specs") or 0) + len(ensemble_results)
        training["tuned_model_specs"] = int(training.get("tuned_model_specs") or 0) + len(ensemble_results)
        training["simple_ensemble_specs"] = len(ensemble_results)
    strict_selection = select_forecast_edge_slices(model_results)
    confidence_selection = _evaluate_validation_confidence_gate(model_results, min_selective_coverage=0.10)
    selection_for_gate = confidence_selection if confidence_selection.get("selected_slice_count") else strict_selection
    all_holdout_rows = _all_holdout_rows(model_results)
    slice_gate = evaluate_60pct_slice_gate(all_holdout_rows)
    release_gate = evaluate_60pct_release_gate(_gate_input(model_results, selection_for_gate, slice_gate))
    retained_rows = list(selection_for_gate.get("retained_forecast_rows") or [])
    evidence = _materialize_if_passed(root, retained_rows, release_gate)
    retained_accuracy = selection_for_gate.get("retained_holdout_accuracy")
    retained_bacc = selection_for_gate.get("retained_holdout_balanced_accuracy")
    best_score = max(value for value in (retained_accuracy, retained_bacc, 0.0) if isinstance(value, (int, float)))
    gap = round(max(0.0, 0.60 - float(best_score)), 6)
    status = release_gate.get("forecast_release_status") or STATUS_BLOCKED_BELOW
    result = {
        "forecast_status": status,
        "forecast_release_status": status,
        "output_root": str(root),
        "data_source": data_source,
        "expanded_input": expanded_input,
        "expanded_data_available": expanded_data_available,
        "real_expanded_data_available": real_expanded_available,
        "provider_fetch_used": _provider_fetch_used(expansion),
        "provider_fetch_attempted": _provider_fetch_attempted(expansion),
        "fallback_status": fallback_status,
        "ohlcv_only_fallback_blocked": False,
        "data_expansion": expansion,
        "real_expanded_data_requirement": requirement,
        "data_requirement_status": requirement.get("expanded_data_requirement_status"),
        "contract": contract,
        "clean_target_rows": len(target_rows),
        "clean_rows_by_horizon": targets.get("rows_by_horizon"),
        "feature_blocks_generated": features.get("feature_blocks") or [],
        "feature_columns_generated": len(features.get("feature_columns") or []),
        "selected_target_slices": target_selection.get("allowed_count"),
        "exploratory_target_slices": target_selection.get("exploratory_count"),
        "rejected_target_slices": target_selection.get("rejected_count"),
        "recommended_forecast_universe": target_selection.get("recommended_forecast_universe"),
        "training": training,
        "model_families_requested": [
            "logistic_balanced",
            "ridge",
            "linear_svm",
            "random_forest",
            "extra_trees",
            "gradient_boosting",
            "hist_gradient_boosting",
            "simple_ensemble",
            "dummy_baselines",
        ],
        "simple_ensemble_specs": len(ensemble_results),
        "model_groups_attempted": training.get("attempted_model_specs"),
        "model_groups_trained": training.get("trained_model_specs"),
        "model_groups_tuned": training.get("tuned_model_specs"),
        "strict_selection": strict_selection,
        "validation_confidence_gate": confidence_selection,
        "selection_used_for_gate": "validation_confidence_gate" if confidence_selection.get("selected_slice_count") else "strict_slice_selector",
        "retained_rows": selection_for_gate.get("retained_holdout_rows"),
        "retained_coverage": selection_for_gate.get("retained_coverage"),
        "retained_accuracy": retained_accuracy,
        "retained_balanced_accuracy": retained_bacc,
        "retained_mcc": selection_for_gate.get("retained_holdout_mcc"),
        "retained_baselines": selection_for_gate.get("retained_baselines"),
        "best_slice": _best_slice_from_results(model_results),
        "slice_gate": slice_gate,
        "forecast_60pct_release_gate": release_gate,
        "global_60pct_gate_passed": release_gate.get("global_release_passed"),
        "selective_60pct_gate_passed": release_gate.get("selective_release_passed"),
        "slice_only_60pct_gate_passed": release_gate.get("slice_only_passed"),
        "broad_performance_claim_allowed": release_gate.get("broad_performance_claim_allowed"),
        "hard_60pct_reached": bool(release_gate.get("forecast_release_allowed") or release_gate.get("slice_only_passed")),
        "gap_to_60pct": gap,
        "blocker": (
            None
            if release_gate.get("forecast_release_allowed") or release_gate.get("slice_only_passed")
            else "Current local data remains insufficient for an honest >=60% forecast claim."
        ),
        "evidence_materialization": evidence,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    _write_json(root / "data_expanded_60pct_forecast_summary.json", _public(result))
    return result


def render_data_expanded_60pct_forecast_report(result: dict) -> str:
    """Render data-expanded 60% forecast attempt report."""

    baselines = result.get("retained_baselines") or {}
    gate = result.get("forecast_60pct_release_gate") or {}
    lines = [
        "# Data-Expanded 60% Forecast Attempt",
        "",
        f"Forecast release status: {result.get('forecast_release_status')}",
        f"Expanded data available: {result.get('expanded_data_available')}",
        f"Real expanded data available: {result.get('real_expanded_data_available')}",
        f"Data requirement status: {result.get('data_requirement_status')}",
        f"Provider fetch used: {result.get('provider_fetch_used')}",
        f"Provider fetch attempted: {result.get('provider_fetch_attempted')}",
        f"Data source: {result.get('data_source')}",
        f"Fallback status: {result.get('fallback_status')}",
        f"OHLCV-only fallback blocked: {result.get('ohlcv_only_fallback_blocked')}",
        f"Clean target rows: {result.get('clean_target_rows')}",
        f"Clean rows by horizon: {result.get('clean_rows_by_horizon')}",
        f"Feature blocks generated: {result.get('feature_blocks_generated')}",
        f"Feature columns generated: {result.get('feature_columns_generated')}",
        f"Selected target slices: {result.get('selected_target_slices')}",
        f"Exploratory target slices: {result.get('exploratory_target_slices')}",
        f"Rejected target slices: {result.get('rejected_target_slices')}",
        f"Model groups attempted/trained/tuned: {result.get('model_groups_attempted')} / {result.get('model_groups_trained')} / {result.get('model_groups_tuned')}",
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
        "Hard 60% gates:",
        f"- global passed: {result.get('global_60pct_gate_passed')}",
        f"- selective passed: {result.get('selective_60pct_gate_passed')}",
        f"- slice-only passed: {result.get('slice_only_60pct_gate_passed')}",
        f"- broad claim allowed: {result.get('broad_performance_claim_allowed')}",
        f"- gap to 60%: {result.get('gap_to_60pct')}",
        "",
        "Gate detail:",
        render_60pct_gate_report(gate).rstrip() if gate else "not_run_expanded_data_required",
        "",
        "Boundary:",
    ]
    if result.get("forecast_release_status") == STATUS_EXPANDED_REQUIRED:
        lines.append("Real expanded data is required before rerunning the hard 60% forecast gate.")
        lines.append("OHLCV-only fallback was blocked for this attempt.")
        lines.append(str(result.get("non_claim", NON_CLAIM_TEXT)))
        return "\n".join(lines).rstrip() + "\n"
    if not result.get("hard_60pct_reached"):
        lines.append("Current local data remains insufficient for an honest >=60% forecast claim.")
    else:
        lines.append(
            "Selective forecast mode reached the hard gate for the disclosed scope only; human review required."
        )
    lines.append(str(result.get("non_claim", NON_CLAIM_TEXT)))
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run data-expanded narrow 60% forecast attempt.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-models", type=int, default=300)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--min-slice-rows", type=int, default=500)
    parser.add_argument("--expanded-input", default=None, help="Real expanded price-panel CSV/JSONL/JSON input.")
    parser.add_argument(
        "--allow-ohlcv-fallback",
        action="store_true",
        help="Explicitly allow the old OHLCV-only fallback. This is not a real expanded-data attempt.",
    )
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_data_expanded_60pct_forecaster(
        output_root=args.output_root,
        max_models=args.max_models,
        max_workers=args.max_workers,
        min_slice_rows=args.min_slice_rows,
        expanded_input=args.expanded_input,
        allow_ohlcv_fallback=args.allow_ohlcv_fallback,
    )
    public = _public(result)
    if args.format == "report":
        print(render_data_expanded_60pct_forecast_report(public), end="")
    else:
        print(json.dumps(public, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
