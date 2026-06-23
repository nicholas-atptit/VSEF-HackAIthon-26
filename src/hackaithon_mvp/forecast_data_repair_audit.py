"""Data-quality audit for local forecast repair rows."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_actual_artifact_discovery import discover_forecast_actual_artifacts
from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_update": True,
    "diagnostic_repair_audit_only": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast data repair audit only; it identifies row-quality risks in explicit local rows."
BINARY_DIRECTIONS = {UP, DOWN}


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _raw(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw")
    return raw if isinstance(raw, dict) else row


def _actual_timestamp(row: dict[str, Any]) -> Any:
    raw = _raw(row)
    return (
        raw.get("actual_timestamp")
        or raw.get("future_timestamp")
        or raw.get("label_timestamp")
        or raw.get("target_timestamp")
    )


def _slice_key(row: dict[str, Any], fields: tuple[str, ...] = ("ticker", "horizon")) -> str:
    return "|".join(str(row.get(field) or "unspecified") for field in fields)


def _prediction_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("ticker") or "unspecified"),
        str(row.get("model_id") or "unspecified"),
        str(row.get("horizon") or "unspecified"),
        str(row.get("forecast_timestamp") or "unspecified"),
    )


def _horizon_steps(value: Any) -> int:
    try:
        steps = int(float(value))
    except (TypeError, ValueError):
        return 1
    return max(1, steps)


def _severity(duplicate_row_count: int, total_rows: int) -> str:
    if duplicate_row_count <= 0:
        return "none"
    ratio = duplicate_row_count / total_rows if total_rows else 0.0
    if duplicate_row_count >= 100 or ratio >= 0.05:
        return "high"
    if duplicate_row_count >= 10 or ratio >= 0.01:
        return "medium"
    return "low"


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _ordered_group_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("ticker") or ""),
            str(row.get("horizon") or ""),
            str(row.get("model_id") or ""),
            _parse_time(row.get("forecast_timestamp")) or datetime.min,
            str(row.get("forecast_timestamp") or ""),
            int(row.get("source_index") or 0),
        ),
    )


def _step_position(row: dict[str, Any], fallback: int) -> int:
    raw = _raw(row)
    for key in ("deoverlap_step_index", "_deoverlap_step_index", "source_step_index", "bar_index"):
        value = raw.get(key, row.get(key))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return fallback


def _overlap_summaries(normalized: tuple[dict[str, Any], ...]) -> tuple[dict[str, dict], dict[str, dict]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[_slice_key(row, ("ticker", "horizon", "model_id"))].append(row)

    by_horizon: dict[str, dict[str, Any]] = {}
    by_ticker_horizon: dict[str, dict[str, Any]] = {}
    horizon_counts: dict[str, Counter[str]] = defaultdict(Counter)
    ticker_horizon_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for group_rows in grouped.values():
        ordered = _ordered_group_rows(group_rows)
        last_position: int | None = None
        last_time: datetime | None = None
        for index, row in enumerate(ordered):
            horizon = str(row.get("horizon") or "unspecified")
            ticker_horizon = _slice_key(row, ("ticker", "horizon"))
            steps = _horizon_steps(row.get("horizon"))
            current_position = _step_position(row, index)
            current_time = _parse_time(row.get("forecast_timestamp"))
            overlapped = False
            if last_position is not None:
                overlapped = current_position - last_position < steps
            elif last_time is not None and current_time is not None:
                overlapped = (current_time - last_time).days < steps
            horizon_counts[horizon]["rows"] += 1
            ticker_horizon_counts[ticker_horizon]["rows"] += 1
            if overlapped:
                horizon_counts[horizon]["overlap_rows"] += 1
                ticker_horizon_counts[ticker_horizon]["overlap_rows"] += 1
            last_position = current_position
            last_time = current_time

    for horizon, counts in sorted(horizon_counts.items()):
        rows = int(counts["rows"])
        overlap_rows = int(counts["overlap_rows"])
        by_horizon[horizon] = {
            "row_count": rows,
            "overlap_row_count": overlap_rows,
            "overlap_rate": _ratio(overlap_rows, rows),
        }
    for key, counts in sorted(ticker_horizon_counts.items()):
        rows = int(counts["rows"])
        overlap_rows = int(counts["overlap_rows"])
        by_ticker_horizon[key] = {
            "row_count": rows,
            "overlap_row_count": overlap_rows,
            "overlap_rate": _ratio(overlap_rows, rows),
            "excessive_overlap": rows >= 2 and _ratio(overlap_rows, rows) > 0.20,
        }
    return by_horizon, by_ticker_horizon


def _transition_metrics(normalized: tuple[dict[str, Any], ...], fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[_slice_key(row, fields)].append(row)

    output = {}
    for key, rows in sorted(grouped.items()):
        ordered = _ordered_group_rows(rows)
        transitions = Counter()
        same = 0
        count = 0
        previous: str | None = None
        labels = Counter(str(row.get("actual_direction")) for row in ordered if row.get("actual_direction") in BINARY_DIRECTIONS)
        for row in ordered:
            actual = row.get("actual_direction")
            if actual not in BINARY_DIRECTIONS:
                continue
            if previous is not None:
                transitions[f"{previous}->{actual}"] += 1
                same += 1 if previous == actual else 0
                count += 1
            previous = str(actual)
        total = sum(labels.values())
        majority = max(labels.values()) if labels else 0
        output[key] = {
            "row_count": len(ordered),
            "binary_label_count": total,
            "transition_count": count,
            "same_label_transition_rate": _ratio(same, count),
            "label_transition_rate": _ratio(count - same, count),
            "label_distribution": dict(sorted(labels.items())),
            "majority_class_ratio": _ratio(majority, total),
        }
    return output


def identify_duplicate_prediction_keys(rows: list[dict]) -> dict:
    """Count duplicate ticker/model/horizon/timestamp prediction keys."""

    normalized = normalize_forecast_actual_rows(rows)
    keys = Counter(_prediction_key(row) for row in normalized)
    duplicate_keys = {key: count for key, count in keys.items() if count > 1}
    duplicate_row_count = sum(count - 1 for count in duplicate_keys.values())
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "duplicate_key_count": len(duplicate_keys),
        "duplicate_row_count": duplicate_row_count,
        "duplicate_key_severity": _severity(duplicate_row_count, len(normalized)),
        "sample_duplicate_keys": [
            {
                "ticker": key[0],
                "model_id": key[1],
                "horizon": key[2],
                "forecast_timestamp": key[3],
                "count": count,
            }
            for key, count in list(sorted(duplicate_keys.items(), key=lambda item: (-item[1], item[0])))[:10]
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def identify_overlapping_label_windows(rows: list[dict]) -> dict:
    """Estimate overlapping target-window rows within ticker/horizon/model slices."""

    normalized = normalize_forecast_actual_rows(rows)
    by_horizon, by_ticker_horizon = _overlap_summaries(normalized)
    total_rows = sum(item["row_count"] for item in by_horizon.values())
    overlap_rows = sum(item["overlap_row_count"] for item in by_horizon.values())
    excessive = {
        key: value
        for key, value in by_ticker_horizon.items()
        if value.get("excessive_overlap")
    }
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "overlap_row_count": overlap_rows,
        "overlap_rate": _ratio(overlap_rows, total_rows),
        "overlap_rate_by_horizon": by_horizon,
        "ticker_horizon_rows_with_excessive_overlap": excessive,
        "overlap_warning": bool(excessive),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def identify_unstable_slices(rows: list[dict]) -> dict:
    """Report noisy ticker/horizon slices by overlap, imbalance, and label persistence."""

    normalized = normalize_forecast_actual_rows(rows)
    _, ticker_horizon_overlap = _overlap_summaries(normalized)
    transitions = _transition_metrics(normalized, ("ticker", "horizon"))
    duplicate_counts: dict[str, Counter[str]] = defaultdict(Counter)
    seen: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in normalized:
        key = _prediction_key(row)
        seen[key] += 1
    for key, count in seen.items():
        if count <= 1:
            continue
        duplicate_counts[f"{key[0]}|{key[2]}"]["duplicate_rows"] += count - 1

    slices = {}
    for key in sorted(set(ticker_horizon_overlap) | set(transitions)):
        overlap = ticker_horizon_overlap.get(key, {})
        transition = transitions.get(key, {})
        duplicate_rows = int(duplicate_counts.get(key, Counter()).get("duplicate_rows", 0))
        majority_ratio = transition.get("majority_class_ratio")
        persistence = transition.get("same_label_transition_rate")
        flags = []
        if float(overlap.get("overlap_rate") or 0.0) > 0.20:
            flags.append("excessive_overlap")
        if isinstance(majority_ratio, (int, float)) and majority_ratio >= 0.70:
            flags.append("class_imbalance")
        if isinstance(persistence, (int, float)) and persistence >= 0.85:
            flags.append("high_prior_label_persistence")
        if duplicate_rows:
            flags.append("duplicate_prediction_keys")
        slices[key] = {
            "row_count": max(int(overlap.get("row_count") or 0), int(transition.get("row_count") or 0)),
            "overlap_rate": overlap.get("overlap_rate", 0.0),
            "majority_class_ratio": majority_ratio,
            "same_label_transition_rate": persistence,
            "label_transition_rate": transition.get("label_transition_rate"),
            "duplicate_row_count": duplicate_rows,
            "unstable": bool(flags),
            "instability_flags": flags,
        }
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "unstable_slice_count": sum(1 for item in slices.values() if item["unstable"]),
        "slices": slices,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _timestamp_label_inconsistency(normalized: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    labels_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in normalized:
        actual = row.get("actual_direction")
        if actual in BINARY_DIRECTIONS:
            labels_by_key[
                (
                    str(row.get("ticker") or "unspecified"),
                    str(row.get("horizon") or "unspecified"),
                    str(row.get("forecast_timestamp") or "unspecified"),
                )
            ].add(str(actual))
    inconsistent = {key: labels for key, labels in labels_by_key.items() if len(labels) > 1}
    return {
        "inconsistent_label_timestamp_count": len(inconsistent),
        "sample_inconsistent_label_timestamps": [
            {
                "ticker": key[0],
                "horizon": key[1],
                "forecast_timestamp": key[2],
                "actual_labels": sorted(labels),
            }
            for key, labels in list(sorted(inconsistent.items()))[:10]
        ],
    }


def _timestamp_order_audit(normalized: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    impossible_future = 0
    non_increasing = 0
    missing_actual_timestamp = 0
    for row in normalized:
        actual_value = _actual_timestamp(row)
        actual_time = _parse_time(actual_value)
        forecast_time = _parse_time(row.get("forecast_timestamp"))
        if actual_time is None:
            missing_actual_timestamp += 1
            continue
        if actual_time > now:
            impossible_future += 1
        if forecast_time is not None and forecast_time >= actual_time:
            non_increasing += 1
    return {
        "rows_missing_actual_timestamp": missing_actual_timestamp,
        "rows_with_impossible_future_timestamps": impossible_future,
        "rows_where_forecast_timestamp_ge_actual_timestamp": non_increasing,
    }


def _leakage_score(
    *,
    duplicate: dict[str, Any],
    overlap: dict[str, Any],
    timestamp_order: dict[str, Any],
    inconsistent: dict[str, Any],
    normalized_rows: int,
) -> dict[str, Any]:
    score = 0.0
    duplicate_ratio = (duplicate.get("duplicate_row_count") or 0) / normalized_rows if normalized_rows else 0.0
    overlap_rate = float(overlap.get("overlap_rate") or 0.0)
    timestamp_ratio = (
        (timestamp_order.get("rows_where_forecast_timestamp_ge_actual_timestamp") or 0)
        + (timestamp_order.get("rows_with_impossible_future_timestamps") or 0)
    ) / normalized_rows if normalized_rows else 0.0
    inconsistent_ratio = (inconsistent.get("inconsistent_label_timestamp_count") or 0) / normalized_rows if normalized_rows else 0.0
    score += min(0.35, duplicate_ratio * 3.0)
    score += min(0.35, overlap_rate * 0.7)
    score += min(0.20, timestamp_ratio * 5.0)
    score += min(0.10, inconsistent_ratio * 5.0)
    severity = "low"
    if score >= 0.50 or duplicate.get("duplicate_key_severity") == "high":
        severity = "high"
    elif score >= 0.20:
        severity = "medium"
    return {
        "leakage_risk_score": round(min(score, 1.0), 6),
        "leakage_risk_severity": severity,
        "leakage_warning": severity == "high" or timestamp_order.get("rows_where_forecast_timestamp_ge_actual_timestamp", 0) > 0,
    }


def _repair_actions(result: dict[str, Any]) -> list[str]:
    actions = []
    duplicate = result.get("duplicate_prediction_keys") or {}
    overlap = result.get("overlapping_label_windows") or {}
    timestamp = result.get("timestamp_order") or {}
    unstable = result.get("unstable_slices") or {}
    if duplicate.get("duplicate_row_count"):
        actions.append("remove duplicate ticker/model/horizon/timestamp keys before scoring")
    if overlap.get("overlap_warning"):
        actions.append("de-overlap target windows by retaining rows at least horizon steps apart")
    if timestamp.get("rows_where_forecast_timestamp_ge_actual_timestamp"):
        actions.append("drop rows where forecast timestamp is not earlier than the actual timestamp")
    if timestamp.get("rows_with_impossible_future_timestamps"):
        actions.append("exclude rows whose actual timestamp is beyond the local audit date")
    if unstable.get("unstable_slice_count"):
        actions.append("abstain ticker/horizon slices with unstable labels, imbalance, or excessive overlap")
    actions.append("report coverage together with accuracy and keep human review required")
    return actions


def audit_forecast_dataset_integrity(rows: list[dict]) -> dict:
    """Run the complete forecast data repair audit over local rows."""

    normalized = normalize_forecast_actual_rows(rows)
    duplicate = identify_duplicate_prediction_keys(rows)
    overlap = identify_overlapping_label_windows(rows)
    unstable = identify_unstable_slices(rows)
    transitions_by_ticker_horizon = _transition_metrics(normalized, ("ticker", "horizon"))
    class_counts = Counter(str(row.get("actual_direction")) for row in normalized if row.get("actual_direction") in BINARY_DIRECTIONS)
    total_labels = sum(class_counts.values())
    majority = max(class_counts.values()) if class_counts else 0
    inconsistent = _timestamp_label_inconsistency(normalized)
    timestamp_order = _timestamp_order_audit(normalized)
    leakage = _leakage_score(
        duplicate=duplicate,
        overlap=overlap,
        timestamp_order=timestamp_order,
        inconsistent=inconsistent,
        normalized_rows=len(normalized),
    )
    result = {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "duplicate_prediction_keys": duplicate,
        "overlapping_label_windows": overlap,
        "unstable_slices": unstable,
        "label_transition_rates": transitions_by_ticker_horizon,
        "class_imbalance": {
            "binary_label_count": total_labels,
            "label_distribution": dict(sorted(class_counts.items())),
            "majority_class_ratio": _ratio(majority, total_labels),
            "imbalance_warning": total_labels > 0 and _ratio(majority, total_labels) >= 0.70,
        },
        "prior_label_persistence": {
            "global_same_label_transition_rate": _global_persistence(transitions_by_ticker_horizon),
            "by_ticker_horizon": transitions_by_ticker_horizon,
        },
        "timestamp_label_consistency": inconsistent,
        "timestamp_order": timestamp_order,
        **leakage,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    result["recommended_repair_actions"] = _repair_actions(result)
    return result


def _global_persistence(transitions: dict[str, dict[str, Any]]) -> float | None:
    same = 0.0
    count = 0
    for item in transitions.values():
        transition_count = int(item.get("transition_count") or 0)
        rate = item.get("same_label_transition_rate")
        if isinstance(rate, (int, float)):
            same += float(rate) * transition_count
            count += transition_count
    return round(same / count, 6) if count else None


def render_forecast_data_repair_report(result: dict) -> str:
    """Render a compact forecast data repair audit report."""

    duplicate = result.get("duplicate_prediction_keys") or {}
    overlap = result.get("overlapping_label_windows") or {}
    timestamp = result.get("timestamp_order") or {}
    imbalance = result.get("class_imbalance") or {}
    unstable = result.get("unstable_slices") or {}
    lines = [
        "# Forecast Data Repair Audit",
        "",
        f"Audit status: {result.get('audit_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Normalized rows: {result.get('normalized_rows')}",
        f"Duplicate key count: {duplicate.get('duplicate_key_count')}",
        f"Duplicate rows: {duplicate.get('duplicate_row_count')}",
        f"Duplicate severity: {duplicate.get('duplicate_key_severity')}",
        f"Overlap rows: {overlap.get('overlap_row_count')}",
        f"Overlap rate: {overlap.get('overlap_rate')}",
        f"Unstable ticker/horizon slices: {unstable.get('unstable_slice_count')}",
        f"Class distribution: {imbalance.get('label_distribution')}",
        f"Majority class ratio: {imbalance.get('majority_class_ratio')}",
        f"Rows with impossible future timestamps: {timestamp.get('rows_with_impossible_future_timestamps')}",
        f"Rows where forecast timestamp >= actual timestamp: {timestamp.get('rows_where_forecast_timestamp_ge_actual_timestamp')}",
        f"Leakage risk score: {result.get('leakage_risk_score')}",
        f"Leakage warning: {result.get('leakage_warning')}",
        "",
        "Recommended repair actions:",
    ]
    lines.extend([f"- {action}" for action in result.get("recommended_repair_actions", [])] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "This audit diagnoses local forecast-vs-actual rows and does not alter model outputs.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _load_discovered_rows() -> list[dict[str, Any]]:
    discovery = discover_forecast_actual_artifacts(repo_root=".")
    for candidate in discovery.get("candidate_files", []):
        if not candidate.get("usable_for_accuracy"):
            continue
        try:
            return load_forecast_accuracy_rows(str(candidate["path"]))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return []


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit forecast repair data quality.")
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
        rows = _load_discovered_rows() if args.discover else load_forecast_accuracy_rows(args.input) if args.input else []
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    result = audit_forecast_dataset_integrity(rows)
    if args.format == "report":
        print(render_forecast_data_repair_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
