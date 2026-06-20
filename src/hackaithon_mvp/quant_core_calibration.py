"""Score and confidence calibration diagnostics for local realized rows."""

from __future__ import annotations

from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import DIRECTIONAL_DIAGNOSTICS, validate_forecast_actual_row
from src.hackaithon_mvp.quant_core_performance_attribution import NON_CLAIM_TEXT


MATERIAL_INVERSION_GAP = 0.05
TOP_SLICE_COUNT = 50
MATERIAL_TOP_SLICE_GAP = 0.05


def _safe_optional_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _is_correct(row: dict[str, Any]) -> bool:
    if row["forecast_diagnostic"] == "positive_bias":
        return row["actual_direction_label"] == "positive"
    if row["forecast_diagnostic"] == "negative_bias":
        return row["actual_direction_label"] == "negative"
    return False


def _directional_metrics(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    correct_count = len([row for row in rows if _is_correct(row)])
    positive_predictions = tuple(row for row in rows if row["forecast_diagnostic"] == "positive_bias")
    negative_predictions = tuple(row for row in rows if row["forecast_diagnostic"] == "negative_bias")
    actual_positive = tuple(row for row in rows if row["actual_direction_label"] == "positive")
    actual_negative = tuple(row for row in rows if row["actual_direction_label"] == "negative")
    positive_recall = _ratio(
        len([row for row in actual_positive if row["forecast_diagnostic"] == "positive_bias"]),
        len(actual_positive),
    )
    negative_recall = _ratio(
        len([row for row in actual_negative if row["forecast_diagnostic"] == "negative_bias"]),
        len(actual_negative),
    )
    balanced_accuracy = None
    if positive_recall is not None and negative_recall is not None:
        balanced_accuracy = round((positive_recall + negative_recall) / 2, 6)
    return {
        "directional_accuracy": _ratio(correct_count, len(rows)),
        "balanced_directional_accuracy": balanced_accuracy,
        "positive_precision": _ratio(
            len([row for row in positive_predictions if row["actual_direction_label"] == "positive"]),
            len(positive_predictions),
        ),
        "negative_precision": _ratio(
            len([row for row in negative_predictions if row["actual_direction_label"] == "negative"]),
            len(negative_predictions),
        ),
    }


def _bin_rows(rows: tuple[dict[str, Any], ...], bin_count: int) -> list[tuple[dict[str, Any], ...]]:
    if not rows:
        return []
    bin_count = max(1, min(bin_count, len(rows)))
    return [tuple(rows[index * len(rows) // bin_count : (index + 1) * len(rows) // bin_count]) for index in range(bin_count)]


def _calibration_report(rows: tuple[dict, ...], field: str, bins: int) -> dict:
    if bins <= 0:
        raise ValueError("bins must be positive")

    normalized_rows = tuple(validate_forecast_actual_row(row) for row in rows)
    scored_rows: list[dict[str, Any]] = []
    for row in normalized_rows:
        if row["forecast_diagnostic"] not in DIRECTIONAL_DIAGNOSTICS:
            continue
        score_value = _safe_optional_float(row.get(field))
        if score_value is None:
            continue
        enriched = dict(row)
        enriched["_calibration_value"] = score_value
        scored_rows.append(enriched)

    sorted_rows = tuple(sorted(scored_rows, key=lambda row: (row["_calibration_value"], row["ticker"], row["prediction_timestamp"])))
    bin_payloads = []
    for index, bin_rows in enumerate(_bin_rows(sorted_rows, bins)):
        values = [row["_calibration_value"] for row in bin_rows]
        metrics = _directional_metrics(bin_rows)
        bin_payloads.append(
            {
                "bin_index": index,
                "row_count": len(bin_rows),
                "min_value": round(min(values), 10),
                "max_value": round(max(values), 10),
                "directional_accuracy": metrics["directional_accuracy"],
                "balanced_directional_accuracy": metrics["balanced_directional_accuracy"],
            }
        )

    bottom_accuracy = bin_payloads[0]["directional_accuracy"] if bin_payloads else None
    top_accuracy = bin_payloads[-1]["directional_accuracy"] if bin_payloads else None
    global_metrics = _directional_metrics(sorted_rows)
    top_slice = sorted_rows[-min(TOP_SLICE_COUNT, len(sorted_rows)) :] if sorted_rows else tuple()
    top_slice_metrics = _directional_metrics(top_slice)
    top_slice_accuracy = top_slice_metrics["directional_accuracy"] if top_slice else None
    top_slice_underperformed = (
        top_slice_accuracy is not None
        and global_metrics["directional_accuracy"] is not None
        and top_slice_accuracy < global_metrics["directional_accuracy"] - MATERIAL_TOP_SLICE_GAP
    )
    inversion_suspected = (
        top_accuracy is not None
        and bottom_accuracy is not None
        and top_accuracy < bottom_accuracy - MATERIAL_INVERSION_GAP
    )
    directional_accuracies = [
        item["directional_accuracy"] for item in bin_payloads if item["directional_accuracy"] is not None
    ]
    if len(directional_accuracies) < 2:
        monotonicity_check = "insufficient_scored_rows"
    elif inversion_suspected:
        monotonicity_check = "top_bin_below_bottom_bin"
    elif all(left <= right for left, right in zip(directional_accuracies, directional_accuracies[1:])):
        monotonicity_check = "non_decreasing_by_score"
    else:
        monotonicity_check = "not_monotonic_by_score"

    ranking_warning = None
    if not bin_payloads:
        ranking_warning = "score_field_missing_or_unusable"
    elif inversion_suspected:
        ranking_warning = "score_may_be_inverted_or_not_calibrated"
    elif top_slice_underperformed:
        ranking_warning = "score_not_calibrated_for_top_slice_selection"

    return {
        "field": field,
        "rows_total": len(normalized_rows),
        "eligible_rows": len(sorted_rows),
        "bins": bin_payloads,
        "global_accuracy": global_metrics["directional_accuracy"],
        "top_bin_accuracy": top_accuracy,
        "bottom_bin_accuracy": bottom_accuracy,
        "top_slice_row_count": len(top_slice),
        "top_slice_accuracy": top_slice_accuracy,
        "top_slice_balanced_directional_accuracy": top_slice_metrics["balanced_directional_accuracy"] if top_slice else None,
        "top_slice_warning": "top_scored_slice_underperformed_global" if top_slice_underperformed else None,
        "monotonicity_check": monotonicity_check,
        "ranking_warning": ranking_warning,
        "inversion_suspected": inversion_suspected,
        "non_claim": NON_CLAIM_TEXT,
    }


def build_score_calibration_report(
    rows: tuple[dict, ...],
    score_field: str = "diagnostic_score",
    bins: int = 10,
) -> dict:
    """Assess whether a score field ranks directional diagnostics usefully."""

    return _calibration_report(rows, score_field, bins)


def build_confidence_calibration_report(
    rows: tuple[dict, ...],
    confidence_field: str = "confidence",
    bins: int = 10,
) -> dict:
    """Assess whether a confidence field ranks directional diagnostics usefully."""

    return _calibration_report(rows, confidence_field, bins)
