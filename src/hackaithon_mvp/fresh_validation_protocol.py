"""Fresh validation protocol helpers for local forecast repair."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import load_forecast_accuracy_rows, normalize_forecast_actual_rows


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "time_split_required": True,
    "holdout_used_once_for_reporting": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Fresh validation protocol marks repaired evaluation as post-hoc when a prior final holdout was inspected."


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _raw(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw")
    return dict(raw) if isinstance(raw, dict) else dict(row)


def _group_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("ticker") or "unspecified"), str(row.get("horizon") or "unspecified")


def _sort_key(row: dict[str, Any]) -> tuple:
    return (
        _parse_time(row.get("forecast_timestamp")) or _parse_time(row.get("timestamp")) or datetime.min,
        str(row.get("forecast_timestamp") or row.get("timestamp") or ""),
        str(row.get("model_id") or ""),
        int(row.get("source_index") or 0),
    )


def _validate_fractions(train_fraction: float, validation_fraction: float, holdout_fraction: float) -> None:
    values = (train_fraction, validation_fraction, holdout_fraction)
    if any(value <= 0 for value in values):
        raise ValueError("split fractions must be positive")
    if abs(sum(values) - 1.0) > 1e-6:
        raise ValueError("split fractions must sum to 1.0")


def build_three_way_time_split(
    rows: list[dict],
    *,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
    holdout_fraction: float = 0.20,
) -> dict:
    """Split rows by time within ticker/horizon groups."""

    _validate_fractions(train_fraction, validation_fraction, holdout_fraction)
    normalized = list(normalize_forecast_actual_rows(rows))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[_group_key(row)].append(row)

    train_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    holdout_rows: list[dict[str, Any]] = []
    group_summaries = []
    for group, group_rows in sorted(grouped.items()):
        ordered = sorted(group_rows, key=_sort_key)
        n_rows = len(ordered)
        if n_rows == 1:
            train_end = 0
            validation_end = 0
        elif n_rows == 2:
            train_end = 1
            validation_end = 1
        else:
            train_end = int(n_rows * train_fraction)
            validation_end = train_end + int(n_rows * validation_fraction)
            train_end = min(max(train_end, 1), n_rows - 2)
            validation_end = min(max(validation_end, train_end + 1), n_rows - 1)
        group_train = ordered[:train_end]
        group_validation = ordered[train_end:validation_end]
        group_holdout = ordered[validation_end:]
        train_rows.extend(_raw(row) for row in group_train)
        validation_rows.extend(_raw(row) for row in group_validation)
        holdout_rows.extend(_raw(row) for row in group_holdout)
        group_summaries.append(
            {
                "ticker": group[0],
                "horizon": group[1],
                "input_rows": n_rows,
                "train_rows": len(group_train),
                "validation_rows": len(group_validation),
                "holdout_rows": len(group_holdout),
                "first_timestamp": str(ordered[0].get("forecast_timestamp")) if ordered else None,
                "last_timestamp": str(ordered[-1].get("forecast_timestamp")) if ordered else None,
            }
        )
    split_status = "ready" if train_rows and validation_rows and holdout_rows else "not_ready_insufficient_time_rows"
    return {
        "split_status": split_status,
        "validation_protocol_status": "post_hoc_repair_validation",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "train_fraction": train_fraction,
        "validation_fraction": validation_fraction,
        "holdout_fraction": holdout_fraction,
        "train_rows": train_rows,
        "validation_rows": validation_rows,
        "holdout_rows": holdout_rows,
        "train_row_count": len(train_rows),
        "validation_row_count": len(validation_rows),
        "holdout_row_count": len(holdout_rows),
        "group_summaries": group_summaries,
        "training_use": "model_fit_only",
        "validation_use": "slice_and_policy_selection",
        "holdout_use": "final_reporting_once",
        "previous_holdout_already_inspected": True,
        "truly_fresh_holdout_exists": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def build_nested_walk_forward_protocol(rows: list[dict]) -> dict:
    """Build deterministic nested walk-forward fold metadata by ticker/horizon."""

    normalized = list(normalize_forecast_actual_rows(rows))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[_group_key(row)].append(row)

    folds = []
    for group, group_rows in sorted(grouped.items()):
        ordered = sorted(group_rows, key=_sort_key)
        n_rows = len(ordered)
        if n_rows < 5:
            folds.append(
                {
                    "ticker": group[0],
                    "horizon": group[1],
                    "fold_status": "not_ready_insufficient_rows",
                    "input_rows": n_rows,
                }
            )
            continue
        fold_count = min(3, max(1, n_rows // 100))
        for fold_index in range(fold_count):
            train_end = max(1, int(n_rows * (0.50 + fold_index * 0.10)))
            validation_end = min(n_rows - 1, train_end + max(1, int(n_rows * 0.15)))
            holdout_end = min(n_rows, validation_end + max(1, int(n_rows * 0.15)))
            if validation_end >= holdout_end:
                continue
            folds.append(
                {
                    "ticker": group[0],
                    "horizon": group[1],
                    "fold_index": fold_index,
                    "fold_status": "ready",
                    "train_start_index": 0,
                    "train_end_index": train_end,
                    "validation_start_index": train_end,
                    "validation_end_index": validation_end,
                    "holdout_start_index": validation_end,
                    "holdout_end_index": holdout_end,
                    "train_rows": train_end,
                    "validation_rows": validation_end - train_end,
                    "holdout_rows": holdout_end - validation_end,
                }
            )
    ready_folds = [fold for fold in folds if fold.get("fold_status") == "ready"]
    return {
        "protocol_status": "ready" if ready_folds else "not_ready_insufficient_time_rows",
        "validation_protocol_status": "post_hoc_repair_validation",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "fold_count": len(folds),
        "ready_fold_count": len(ready_folds),
        "folds": folds,
        "previous_holdout_already_inspected": True,
        "truly_fresh_holdout_exists": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_fresh_validation_protocol_report(result: dict) -> str:
    """Render a compact fresh validation protocol report."""

    lines = [
        "# Fresh Validation Protocol",
        "",
        f"Protocol status: {result.get('split_status', result.get('protocol_status'))}",
        f"Validation status: {result.get('validation_protocol_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Train rows: {result.get('train_row_count')}",
        f"Validation rows: {result.get('validation_row_count')}",
        f"Holdout rows: {result.get('holdout_row_count')}",
        f"Fold count: {result.get('fold_count')}",
        f"Ready folds: {result.get('ready_fold_count')}",
        f"Previous holdout already inspected: {result.get('previous_holdout_already_inspected')}",
        f"Truly fresh holdout exists: {result.get('truly_fresh_holdout_exists')}",
        "",
        "Boundary:",
        "Training, validation, and holdout windows are time-ordered within ticker/horizon groups.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local time-split validation protocol metadata.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--nested", action="store_true")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_forecast_accuracy_rows(args.input)
        result = build_nested_walk_forward_protocol(rows) if args.nested else build_three_way_time_split(rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    public_result = {key: value for key, value in result.items() if key not in {"train_rows", "validation_rows", "holdout_rows"}}
    if args.format == "report":
        print(render_fresh_validation_protocol_report(public_result), end="")
    else:
        print(json.dumps(public_result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
