"""Narrow forecast target selection for data-expanded 60% attempts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PREFERRED_HORIZONS = (1, 5, 10)
PREFERRED_MIN_ROWS = 500
DIAGNOSTIC_MIN_ROWS = 300
EXPLORATORY_MIN_ROWS = 150
MAX_CLASS_SHARE = 0.75
MAX_VALIDATION_HOLDOUT_GAP = 0.15
CLAIM_BOUNDARY = {
    "narrow_target_selection_only": True,
    "validation_holdout_gap_checked_when_available": True,
    "no_forecast_claim": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Narrow target selector recommends local ticker/horizon candidates; final accuracy still requires holdout scoring."


def _direction(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"up", "positive", "1", "+1", "true"}:
        return "up"
    if text in {"down", "negative", "0", "-1", "false"}:
        return "down"
    return None


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _slice_key(row: dict) -> tuple[str, int]:
    ticker = str(row.get("ticker") or "unspecified").strip().upper()
    try:
        horizon = int(row.get("horizon"))
    except (TypeError, ValueError):
        horizon = -1
    return ticker, horizon


def _duplicate_count(rows: list[dict]) -> int:
    counter = Counter(
        (
            str(row.get("ticker") or "").upper(),
            str(row.get("horizon") or ""),
            str(row.get("timestamp") or row.get("forecast_timestamp") or ""),
        )
        for row in rows
    )
    return sum(count - 1 for count in counter.values() if count > 1)


def _overlap_severity(rows: list[dict], horizon: int) -> str:
    if horizon <= 1:
        return "none"
    ordered = sorted(str(row.get("timestamp") or row.get("forecast_timestamp") or "") for row in rows)
    if len(ordered) < 2:
        return "none"
    # If a target builder marked rows non-overlapping, trust that contract.
    if rows and all(row.get("non_overlapping_target") is True for row in rows):
        return "none"
    return "medium"


def _prior_signal(row: dict) -> bool:
    for key in ("prior_signal", "validation_balanced_accuracy", "holdout_balanced_accuracy"):
        value = _safe_float(row.get(key))
        if value is not None and value > 0.52:
            return True
    return False


def _reasons(rows: list[dict], *, min_rows: int) -> list[str]:
    ticker, horizon = _slice_key(rows[0])
    reasons: list[str] = []
    if horizon not in PREFERRED_HORIZONS:
        reasons.append("horizon_not_prioritized")
    if len(rows) < EXPLORATORY_MIN_ROWS:
        reasons.append("rows_below_exploratory_minimum")
    elif len(rows) < DIAGNOSTIC_MIN_ROWS:
        reasons.append("exploratory_rows_only")
    elif len(rows) < min_rows:
        reasons.append("below_preferred_row_count")
    labels = [_direction(row.get("future_direction", row.get("actual_direction"))) for row in rows]
    labels = [label for label in labels if label]
    if len(set(labels)) < 2:
        reasons.append("single_class_slice")
    elif labels:
        majority_share = max(Counter(labels).values()) / len(labels)
        if majority_share > MAX_CLASS_SHARE:
            reasons.append("class_balance_too_extreme")
    duplicates = _duplicate_count(rows)
    if duplicates:
        reasons.append("duplicate_keys_present")
    if _overlap_severity(rows, horizon) == "high":
        reasons.append("overlap_high_severity")
    previous = max((_safe_float(row.get("previous_direction_baseline")) or 0.0 for row in rows), default=0.0)
    candidate = max((_safe_float(row.get("prior_signal")) or 0.0 for row in rows), default=0.0)
    leakage_flag = any(bool(row.get("previous_direction_leakage_risk")) for row in rows)
    if previous and candidate and previous >= candidate and not leakage_flag:
        reasons.append("previous_direction_baseline_dominates")
    validation = max((_safe_float(row.get("validation_balanced_accuracy")) or 0.0 for row in rows), default=0.0)
    holdout = max((_safe_float(row.get("holdout_balanced_accuracy")) or 0.0 for row in rows), default=0.0)
    if validation and holdout and validation - holdout > MAX_VALIDATION_HOLDOUT_GAP:
        reasons.append("validation_holdout_gap_excessive")
    return reasons


def select_narrow_forecast_targets(
    rows: list[dict],
    *,
    min_rows: int = PREFERRED_MIN_ROWS,
    horizons: tuple[int, ...] = PREFERRED_HORIZONS,
) -> dict:
    """Select ticker/horizon candidates before model training."""

    horizon_set = {int(horizon) for horizon in horizons}
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        ticker, horizon = _slice_key(row)
        if horizon in horizon_set:
            grouped[(ticker, horizon)].append(row)

    allowed = []
    rejected = []
    exploratory = []
    for (ticker, horizon), group_rows in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        reasons = _reasons(group_rows, min_rows=min_rows)
        item = {
            "slice_id": f"{ticker}|h{horizon}",
            "ticker": ticker,
            "horizon": horizon,
            "rows": len(group_rows),
            "class_counts": dict(
                Counter(_direction(row.get("future_direction", row.get("actual_direction"))) or "unclassified" for row in group_rows)
            ),
            "duplicate_key_count": _duplicate_count(group_rows),
            "overlap_severity": _overlap_severity(group_rows, horizon),
            "prior_signal_available": any(_prior_signal(row) for row in group_rows),
        }
        if not reasons or reasons == ["below_preferred_row_count"]:
            if len(group_rows) >= DIAGNOSTIC_MIN_ROWS:
                status = "target_candidate_allowed"
                allowed.append({**item, "selection_status": status, "warnings": reasons})
            else:
                exploratory.append({**item, "selection_status": "target_candidate_exploratory", "rejection_reasons": reasons})
        elif "exploratory_rows_only" in reasons and len(group_rows) >= EXPLORATORY_MIN_ROWS:
            exploratory.append({**item, "selection_status": "target_candidate_exploratory", "rejection_reasons": reasons})
        else:
            rejected.append({**item, "selection_status": "target_candidate_rejected", "rejection_reasons": reasons})

    recommended = [
        {"ticker": item["ticker"], "horizon": item["horizon"], "rows": item["rows"]}
        for item in sorted(allowed, key=lambda item: (item["horizon"], -item["rows"], item["ticker"]))
    ]
    return {
        "selection_status": "ready" if allowed else "no_preferred_targets",
        "allowed_target_candidates": allowed,
        "rejected_target_candidates": rejected,
        "exploratory_target_candidates": exploratory,
        "allowed_count": len(allowed),
        "rejected_count": len(rejected),
        "exploratory_count": len(exploratory),
        "recommended_forecast_universe": recommended,
        "rejection_reason_distribution": dict(Counter(reason for item in rejected for reason in item.get("rejection_reasons", []))),
        "preferred_horizons": list(horizon_set),
        "preferred_min_rows": int(min_rows),
        "diagnostic_min_rows": DIAGNOSTIC_MIN_ROWS,
        "exploratory_min_rows": EXPLORATORY_MIN_ROWS,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_narrow_forecast_target_selector_report(result: dict) -> str:
    """Render narrow target selection report."""

    lines = [
        "# Narrow Forecast Target Selector",
        "",
        f"Selection status: {result.get('selection_status')}",
        f"Allowed target candidates: {result.get('allowed_count')}",
        f"Exploratory target candidates: {result.get('exploratory_count')}",
        f"Rejected target candidates: {result.get('rejected_count')}",
        f"Recommended forecast universe: {result.get('recommended_forecast_universe')}",
        "",
        "Top rejection reasons:",
    ]
    reasons = result.get("rejection_reason_distribution") or {}
    lines.extend([f"- {key}: {value}" for key, value in reasons.items()] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Rows 150-299 are exploratory only; rows >=300 are diagnostic candidates.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select narrow ticker/horizon forecast targets.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--min-rows", type=int, default=PREFERRED_MIN_ROWS)
    parser.add_argument("--horizons", default="1,5,10")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    horizons = tuple(int(item.strip()) for item in str(args.horizons).split(",") if item.strip())
    result = select_narrow_forecast_targets(_load_jsonl(args.input), min_rows=args.min_rows, horizons=horizons)
    if args.format == "report":
        print(render_narrow_forecast_target_selector_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
