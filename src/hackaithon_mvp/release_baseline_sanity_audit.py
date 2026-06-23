"""Sanity audits for release accuracy baselines."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

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
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Baseline sanity audit only; high persistence is diagnostic evidence, not a performance claim."


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _binary_direction(value: Any) -> str | None:
    return value if value in {UP, DOWN} else None


def _transition_metrics(rows: list[dict]) -> dict:
    transitions = Counter()
    available = 0
    correct = 0
    unavailable = 0
    non_earlier = 0
    previous_by_group: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        group = (str(row.get("ticker")), str(row.get("horizon")), str(row.get("model_id")))
        previous = previous_by_group.get(group)
        actual = _binary_direction(row.get("actual_direction"))
        if previous is None or actual is None:
            unavailable += 1
            if actual is not None:
                previous_by_group[group] = row
            continue
        previous_actual = _binary_direction(previous.get("actual_direction"))
        if previous_actual is None:
            unavailable += 1
            previous_by_group[group] = row
            continue
        prev_time = _parse_time(previous.get("forecast_timestamp"))
        current_time = _parse_time(row.get("forecast_timestamp"))
        if prev_time is not None and current_time is not None and prev_time >= current_time:
            non_earlier += 1
        transitions[f"{previous_actual}->{actual}"] += 1
        available += 1
        if previous_actual == actual:
            correct += 1
        previous_by_group[group] = row
    return {
        "previous_direction_sample_count": available,
        "previous_direction_unavailable_count": unavailable,
        "previous_direction_accuracy": round(correct / available, 6) if available else None,
        "transition_matrix": dict(sorted(transitions.items())),
        "non_earlier_previous_timestamp_count": non_earlier,
    }


def _duplicate_collisions(rows: list[dict]) -> dict:
    keys = Counter(
        (
            str(row.get("forecast_timestamp")),
            str(row.get("model_id")),
            str(row.get("ticker")),
            str(row.get("horizon")),
        )
        for row in rows
    )
    duplicates = {str(key): count for key, count in keys.items() if count > 1}
    return {
        "duplicate_key_count": len(duplicates),
        "duplicate_row_count": sum(count - 1 for count in keys.values() if count > 1),
        "sample_duplicate_keys": dict(list(duplicates.items())[:10]),
    }


def _group_persistence(rows: list[dict], fields: tuple[str, ...]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = "|".join(str(row.get(field) or "unspecified") for field in fields)
        grouped[key].append(row)
    output = {}
    for key, group_rows in grouped.items():
        metrics = _transition_metrics(group_rows)
        output[key] = {
            "sample_count": metrics["previous_direction_sample_count"],
            "persistence": metrics["previous_direction_accuracy"],
            "warning_high_persistence": (
                isinstance(metrics["previous_direction_accuracy"], (int, float))
                and metrics["previous_direction_accuracy"] > 0.90
            ),
        }
    return dict(sorted(output.items()))


def audit_previous_direction_baseline(rows: list[dict]) -> dict:
    """Audit previous-direction baseline construction within ticker/horizon/model groups."""

    normalized = list(normalize_forecast_actual_rows(rows))
    normalized.sort(key=lambda row: (str(row.get("ticker")), str(row.get("horizon")), str(row.get("model_id")), str(row.get("forecast_timestamp"))))
    metrics = _transition_metrics(normalized)
    duplicates = _duplicate_collisions(normalized)
    persistence = metrics.get("previous_direction_accuracy")
    return {
        "audit_status": "completed" if normalized else "not_ready_no_rows",
        "row_count": len(normalized),
        **metrics,
        **duplicates,
        "baseline_grouping": "ticker+horizon+model_id",
        "warning_high_persistence": isinstance(persistence, (int, float)) and persistence > 0.90,
        "leakage_warning": metrics.get("non_earlier_previous_timestamp_count", 0) > 0,
        "overlap_warning": any(str(row.get("horizon")) in {"20", "40"} for row in normalized),
        "persistence_by_ticker": _group_persistence(normalized, ("ticker",)),
        "persistence_by_horizon": _group_persistence(normalized, ("horizon",)),
        "persistence_by_model": _group_persistence(normalized, ("model_id",)),
        "persistence_by_ticker_horizon_model": _group_persistence(normalized, ("ticker", "horizon", "model_id")),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def audit_release_baselines(rows: list[dict]) -> dict:
    """Run all release baseline sanity audits."""

    previous = audit_previous_direction_baseline(rows)
    return {
        "audit_status": previous.get("audit_status"),
        "previous_direction_baseline": previous,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_release_baseline_sanity_report(result: dict) -> str:
    """Render a compact baseline sanity report."""

    previous = result.get("previous_direction_baseline") or {}
    lines = [
        "# Release Baseline Sanity Audit",
        "",
        f"Audit status: {result.get('audit_status')}",
        f"Previous-direction sample count: {previous.get('previous_direction_sample_count')}",
        f"Previous-direction unavailable count: {previous.get('previous_direction_unavailable_count')}",
        f"Previous-direction accuracy: {previous.get('previous_direction_accuracy')}",
        f"Duplicate key count: {previous.get('duplicate_key_count')}",
        f"Leakage warning: {previous.get('leakage_warning')}",
        f"High persistence warning: {previous.get('warning_high_persistence')}",
        f"Overlap warning: {previous.get('overlap_warning')}",
        f"Transition matrix: {previous.get('transition_matrix')}",
        "",
        "Boundary:",
        "Previous-direction baseline is recomputed strictly within ticker+horizon+model groups.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit local release baseline sanity.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_forecast_accuracy_rows(args.input)
    result = audit_release_baselines(rows)
    if args.format == "report":
        print(render_release_baseline_sanity_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
