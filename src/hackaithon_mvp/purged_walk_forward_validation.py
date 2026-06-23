"""Purged temporal validation helpers for overlapping forecast horizons."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "purged_temporal_validation": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Purged validation reports split diagnostics only; it does not train or update models."


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_time(row: dict) -> tuple[datetime | None, str]:
    return _parse_time(row.get("timestamp") or row.get("forecast_timestamp") or row.get("date")), str(
        row.get("timestamp") or row.get("forecast_timestamp") or row.get("date") or ""
    )


def _group_key(row: dict) -> tuple[str, str]:
    return str(row.get("ticker") or "unspecified"), str(row.get("horizon") or "unspecified")


def _ordered(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (_group_key(row), _row_time(row)[1]))


def _target_end_index(row_index: int, horizon_steps: int) -> int:
    return row_index + max(int(horizon_steps), 1)


def purged_temporal_split(
    rows: list[dict],
    *,
    horizon_steps: int,
    validation_fraction: float = 0.30,
    embargo_steps: int | None = None,
) -> dict:
    """Create a chronological split and purge target-window overlap."""

    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    embargo = max(int(embargo_steps if embargo_steps is not None else horizon_steps), 0)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[_group_key(row)].append(row)
    train_rows: list[dict] = []
    validation_rows: list[dict] = []
    purged_count = 0
    embargoed_count = 0
    group_summaries = []
    for group, group_rows in sorted(grouped.items()):
        ordered = _ordered(group_rows)
        if len(ordered) < 3:
            group_summaries.append({"group": group, "status": "too_few_rows", "row_count": len(ordered)})
            continue
        validation_count = max(1, int(round(len(ordered) * validation_fraction)))
        validation_count = min(validation_count, len(ordered) - 1)
        validation_start = len(ordered) - validation_count
        group_validation = ordered[validation_start:]
        group_train = []
        group_purged = 0
        group_embargoed = 0
        for index, row in enumerate(ordered[:validation_start]):
            target_end = _target_end_index(index, horizon_steps)
            if target_end >= validation_start:
                group_purged += 1
                continue
            if index > validation_start - embargo - 1:
                group_embargoed += 1
                continue
            group_train.append(row)
        train_rows.extend(group_train)
        validation_rows.extend(group_validation)
        purged_count += group_purged
        embargoed_count += group_embargoed
        group_summaries.append(
            {
                "group": "|".join(group),
                "row_count": len(ordered),
                "train_rows": len(group_train),
                "validation_rows": len(group_validation),
                "purged_rows": group_purged,
                "embargoed_rows": group_embargoed,
            }
        )
    return {
        "split_status": "ready" if train_rows and validation_rows else "not_ready_insufficient_rows_after_purge",
        "horizon_steps": int(horizon_steps),
        "embargo_steps": embargo,
        "input_rows": len(rows),
        "train_rows": train_rows,
        "validation_rows": validation_rows,
        "train_row_count": len(train_rows),
        "validation_row_count": len(validation_rows),
        "purged_row_count": purged_count,
        "embargoed_row_count": embargoed_count,
        "group_summaries": group_summaries,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def run_walk_forward_folds(
    rows: list[dict],
    *,
    n_folds: int = 3,
    horizon_steps: int = 40,
    embargo_steps: int | None = None,
) -> dict:
    """Build walk-forward fold diagnostics for existing prediction rows."""

    if n_folds < 1:
        raise ValueError("n_folds must be at least 1")
    ordered = _ordered(rows)
    folds = []
    if not ordered:
        return {
            "walk_forward_status": "not_ready_no_rows",
            "folds": [],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
    for fold_index in range(1, n_folds + 1):
        validation_fraction = min(0.5, max(0.1, fold_index / (n_folds + 1) * 0.3))
        split = purged_temporal_split(
            ordered,
            horizon_steps=horizon_steps,
            validation_fraction=validation_fraction,
            embargo_steps=embargo_steps,
        )
        validation = split["validation_rows"]
        metrics = evaluate_forecast_accuracy(validation)["global"]["directional"] if validation else {}
        folds.append(
            {
                "fold": fold_index,
                "split_status": split["split_status"],
                "train_row_count": split["train_row_count"],
                "validation_row_count": split["validation_row_count"],
                "purged_row_count": split["purged_row_count"],
                "embargoed_row_count": split["embargoed_row_count"],
                "validation_accuracy": metrics.get("accuracy"),
                "validation_balanced_accuracy": metrics.get("balanced_accuracy"),
                "validation_mcc": metrics.get("mcc"),
            }
        )
    ready_folds = [fold for fold in folds if fold["split_status"] == "ready"]
    return {
        "walk_forward_status": "completed" if ready_folds else "not_ready_insufficient_rows_after_purge",
        "n_folds": n_folds,
        "horizon_steps": int(horizon_steps),
        "embargo_steps": int(embargo_steps if embargo_steps is not None else horizon_steps),
        "folds": folds,
        "ready_fold_count": len(ready_folds),
        "status_distribution": dict(Counter(fold["split_status"] for fold in folds)),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_purged_walk_forward_report(result: dict) -> str:
    """Render compact purged validation diagnostics."""

    lines = [
        "# Purged Walk-forward Validation",
        "",
        f"Walk-forward status: {result.get('walk_forward_status')}",
        f"Ready folds: {result.get('ready_fold_count')}",
        f"Horizon steps: {result.get('horizon_steps')}",
        f"Embargo steps: {result.get('embargo_steps')}",
        "",
        "Folds:",
    ]
    for fold in result.get("folds", []):
        lines.append(
            "- fold {fold}: train={train}, validation={validation}, purged={purged}, embargoed={embargoed}, bacc={bacc}".format(
                fold=fold.get("fold"),
                train=fold.get("train_row_count"),
                validation=fold.get("validation_row_count"),
                purged=fold.get("purged_row_count"),
                embargoed=fold.get("embargoed_row_count"),
                bacc=fold.get("validation_balanced_accuracy"),
            )
        )
    if not result.get("folds"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "Fold diagnostics use local rows only and do not perform model updates.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run purged walk-forward diagnostics on local rows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--horizon-steps", type=int, default=40)
    parser.add_argument("--n-folds", type=int, default=3)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    rows = []
    with open(args.input, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    result = run_walk_forward_folds(rows, n_folds=args.n_folds, horizon_steps=args.horizon_steps)
    if args.format == "report":
        print(render_purged_walk_forward_report(result), end="")
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
