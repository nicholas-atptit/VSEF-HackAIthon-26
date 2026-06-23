"""Signal sanity audits for local forecast-vs-actual rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from src.hackaithon_mvp.forecast_actual_artifact_discovery import discover_forecast_actual_artifacts
from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_update": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Signal sanity audit only; it diagnoses label/probability polarity and does not change forecasts."


def _metric(rows: list[dict]) -> dict:
    directional = evaluate_forecast_accuracy(rows)["global"]["directional"]
    return {
        "accuracy": directional.get("accuracy"),
        "balanced_accuracy": directional.get("balanced_accuracy"),
        "mcc": directional.get("mcc"),
        "coverage_count": directional.get("coverage_count"),
        "sample_count": directional.get("sample_count"),
    }


def _flip_row(row: dict) -> dict:
    output = dict(row)
    direction = output.get("predicted_direction")
    if direction == UP:
        output["predicted_direction"] = DOWN
    elif direction == DOWN:
        output["predicted_direction"] = UP
    probability = output.get("predicted_probability")
    if isinstance(probability, (int, float)):
        output["predicted_probability"] = round(1.0 - float(probability), 12)
    return output


def _group_metric(rows: tuple[dict, ...], key: str) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key) or "unspecified"), []).append(row)
    result = {}
    for group_key, group_rows in sorted(grouped.items()):
        original = _metric(group_rows)
        flipped = _metric([_flip_row(row) for row in group_rows])
        result[group_key] = {
            "row_count": len(group_rows),
            "original_balanced_accuracy": original.get("balanced_accuracy"),
            "flipped_balanced_accuracy": flipped.get("balanced_accuracy"),
            "balanced_accuracy_delta": _delta(flipped.get("balanced_accuracy"), original.get("balanced_accuracy")),
            "original_accuracy": original.get("accuracy"),
            "flipped_accuracy": flipped.get("accuracy"),
        }
    return result


def _delta(new_value: Any, old_value: Any) -> float | None:
    if not isinstance(new_value, (int, float)) or not isinstance(old_value, (int, float)):
        return None
    return round(float(new_value) - float(old_value), 6)


def _material_improvement(original: dict, flipped: dict) -> bool:
    original_bacc = original.get("balanced_accuracy")
    flipped_bacc = flipped.get("balanced_accuracy")
    if not isinstance(original_bacc, (int, float)) or not isinstance(flipped_bacc, (int, float)):
        return False
    return flipped_bacc >= 0.51 and flipped_bacc - original_bacc >= 0.02


def audit_label_polarity(rows: list[dict]) -> dict:
    """Summarize actual and predicted label values after schema normalization."""

    normalized = normalize_forecast_actual_rows(rows)
    actual = Counter(str(row.get("actual_direction")) for row in normalized)
    predicted = Counter(str(row.get("predicted_direction")) for row in normalized)
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "row_count": len(normalized),
        "actual_label_values": dict(sorted(actual.items())),
        "predicted_label_values": dict(sorted(predicted.items())),
        "actual_binary_count": actual.get(UP, 0) + actual.get(DOWN, 0),
        "predicted_binary_count": predicted.get(UP, 0) + predicted.get(DOWN, 0),
        "label_mapping": {"up": 1, "down": 0, "flat": "excluded_from_binary_metrics"},
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def audit_probability_polarity(rows: list[dict]) -> dict:
    """Check whether probability columns agree with predicted labels."""

    normalized = normalize_forecast_actual_rows(rows)
    probability_rows = [row for row in normalized if isinstance(row.get("predicted_probability"), (int, float))]
    threshold = 0.5
    ge_threshold = [row for row in probability_rows if float(row["predicted_probability"]) >= threshold]
    lt_threshold = [row for row in probability_rows if float(row["predicted_probability"]) < threshold]
    ge_maps_up = sum(1 for row in ge_threshold if row.get("predicted_direction") == UP)
    ge_maps_down = sum(1 for row in ge_threshold if row.get("predicted_direction") == DOWN)
    lt_maps_down = sum(1 for row in lt_threshold if row.get("predicted_direction") == DOWN)
    lt_maps_up = sum(1 for row in lt_threshold if row.get("predicted_direction") == UP)
    expected_agreement = ge_maps_up + lt_maps_down
    inverted_agreement = ge_maps_down + lt_maps_up
    total = len(probability_rows)
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "probability_row_count": total,
        "threshold": threshold,
        "probability_ge_threshold_count": len(ge_threshold),
        "probability_lt_threshold_count": len(lt_threshold),
        "expected_up_mapping_agreement": round(expected_agreement / total, 6) if total else None,
        "inverted_mapping_agreement": round(inverted_agreement / total, 6) if total else None,
        "probability_ge_threshold_maps_to": "up" if ge_maps_up >= ge_maps_down else "down",
        "probability_lt_threshold_maps_to": "down" if lt_maps_down >= lt_maps_up else "up",
        "possible_probability_polarity_mismatch": bool(total and inverted_agreement > expected_agreement),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def audit_horizon_alignment(rows: list[dict]) -> dict:
    """Check timestamp/future timestamp ordering when future timestamps are available."""

    normalized = normalize_forecast_actual_rows(rows)
    missing_future = 0
    non_increasing = 0
    horizon_counts = Counter(str(row.get("horizon") or "unspecified") for row in normalized)
    for row in normalized:
        raw = row.get("raw") or {}
        future_timestamp = raw.get("future_timestamp") or raw.get("actual_timestamp")
        if not future_timestamp:
            missing_future += 1
            continue
        if str(future_timestamp) <= str(row.get("forecast_timestamp")):
            non_increasing += 1
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "row_count": len(normalized),
        "rows_missing_future_timestamp": missing_future,
        "rows_with_non_increasing_future_timestamp": non_increasing,
        "horizon_distribution": dict(sorted(horizon_counts.items())),
        "horizon_alignment_warning": non_increasing > 0,
        "overlap_caveat": "large horizons can overlap adjacent labels and require purged validation",
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def audit_prediction_flip_rescue(rows: list[dict]) -> dict:
    """Evaluate whether flipping predicted labels would rescue below-random behavior."""

    normalized = normalize_forecast_actual_rows(rows)
    original = _metric(list(normalized))
    flipped_rows = [_flip_row(row) for row in normalized]
    flipped = _metric(flipped_rows)
    original_mcc = original.get("mcc")
    flipped_mcc = flipped.get("mcc")
    polarity_flag = (
        isinstance(original.get("balanced_accuracy"), (int, float))
        and isinstance(flipped.get("balanced_accuracy"), (int, float))
        and original["balanced_accuracy"] < 0.50
        and flipped["balanced_accuracy"] > 0.50
        and isinstance(original_mcc, (int, float))
        and isinstance(flipped_mcc, (int, float))
        and original_mcc < 0
        and flipped_mcc > 0
    )
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "original_metrics": original,
        "flipped_metrics": flipped,
        "accuracy_delta": _delta(flipped.get("accuracy"), original.get("accuracy")),
        "balanced_accuracy_delta": _delta(flipped.get("balanced_accuracy"), original.get("balanced_accuracy")),
        "mcc_delta": _delta(flipped.get("mcc"), original.get("mcc")),
        "flipped_predictions_materially_outperform_original": _material_improvement(original, flipped),
        "possible_label_polarity_mismatch": polarity_flag,
        "per_ticker_flip_benefit": _group_metric(normalized, "ticker"),
        "per_horizon_flip_benefit": _group_metric(normalized, "horizon"),
        "per_model_flip_benefit": _group_metric(normalized, "model_id"),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def run_forecast_signal_sanity_audit(rows: list[dict]) -> dict:
    """Run all signal sanity audits over explicit local rows."""

    label = audit_label_polarity(rows)
    probability = audit_probability_polarity(rows)
    horizon = audit_horizon_alignment(rows)
    flip = audit_prediction_flip_rescue(rows)
    return {
        "audit_status": "completed" if label.get("row_count") else "not_ready_no_rows",
        "label_polarity": label,
        "probability_polarity": probability,
        "horizon_alignment": horizon,
        "prediction_flip_rescue": flip,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_signal_sanity_report(result: dict) -> str:
    """Render a compact signal sanity report."""

    flip = result.get("prediction_flip_rescue") or {}
    original = flip.get("original_metrics") or {}
    flipped = flip.get("flipped_metrics") or {}
    probability = result.get("probability_polarity") or {}
    horizon = result.get("horizon_alignment") or {}
    lines = [
        "# Forecast Signal Sanity Audit",
        "",
        f"Audit status: {result.get('audit_status')}",
        f"Original accuracy: {original.get('accuracy')}",
        f"Original balanced accuracy: {original.get('balanced_accuracy')}",
        f"Original MCC: {original.get('mcc')}",
        f"Flipped accuracy: {flipped.get('accuracy')}",
        f"Flipped balanced accuracy: {flipped.get('balanced_accuracy')}",
        f"Flipped MCC: {flipped.get('mcc')}",
        f"Possible label polarity mismatch: {flip.get('possible_label_polarity_mismatch')}",
        f"Probability mismatch warning: {probability.get('possible_probability_polarity_mismatch')}",
        f"Horizon alignment warning: {horizon.get('horizon_alignment_warning')}",
        "",
        "Boundary:",
        "This audit only compares local forecast-vs-actual rows and optional flipped diagnostics.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _load_discovered_rows() -> list[dict]:
    discovery = discover_forecast_actual_artifacts(repo_root=".")
    rows: list[dict] = []
    for candidate in discovery.get("candidate_files", []):
        if not candidate.get("usable_for_accuracy"):
            continue
        try:
            rows.extend(load_forecast_accuracy_rows(str(candidate["path"])))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if rows:
            break
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit local forecast signal polarity and alignment.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.input:
        rows = load_forecast_accuracy_rows(args.input)
    elif args.discover:
        rows = _load_discovered_rows()
    else:
        parser.error("--input or --discover is required")
    result = run_forecast_signal_sanity_audit(rows)
    if args.format == "report":
        print(render_forecast_signal_sanity_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
