"""Select honest diagnostic champions from validation results."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


MIN_VALIDATION_ROWS = 30
CLAIM_BOUNDARY = {
    "diagnostic_champion_selection_only": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Champion selection is validation-evidence routing only, not a deployment or superiority claim."


def _metric(candidate: dict) -> dict:
    metric = candidate.get("post_tune_validation_metrics") or candidate.get("post_tune_validation") or candidate.get("metrics") or {}
    return metric if isinstance(metric, dict) else {}


def _candidate_key(candidate: dict) -> str:
    return "|".join(
        [
            str(candidate.get("ticker") or "global"),
            str(candidate.get("model_key") or candidate.get("model_id") or "model"),
            str(candidate.get("target") or "target"),
            f"h{candidate.get('horizon') or 'unspecified'}",
        ]
    )


def _validation_rows(candidate: dict) -> int:
    for key in ("validation_rows", "validation_sample_count", "coverage_count", "sample_count"):
        value = candidate.get(key)
        if isinstance(value, int):
            return value
    metric = _metric(candidate)
    return int(metric.get("coverage_count") or metric.get("sample_count") or 0)


def _baselines(candidate: dict) -> dict:
    baseline = candidate.get("baseline_comparison")
    if isinstance(baseline, dict):
        return baseline
    metric = _metric(candidate)
    nested = metric.get("baseline_comparison")
    return nested if isinstance(nested, dict) else {}


def _score(candidate: dict) -> float:
    metric = _metric(candidate)
    value = metric.get("balanced_accuracy")
    return float(value) if isinstance(value, (int, float)) else -1.0


def _reject_reasons(candidate: dict) -> list[str]:
    reasons = []
    metric = _metric(candidate)
    score = metric.get("balanced_accuracy")
    rows = _validation_rows(candidate)
    baselines = _baselines(candidate)
    majority = baselines.get("majority_class_baseline_accuracy")
    previous = baselines.get("previous_direction_baseline_accuracy")
    if rows < MIN_VALIDATION_ROWS:
        reasons.append("insufficient_validation_rows")
    if not isinstance(score, (int, float)):
        reasons.append("balanced_accuracy_unavailable")
    elif score <= 0.5:
        reasons.append("does_not_beat_random_baseline")
    if isinstance(majority, (int, float)) and isinstance(score, (int, float)) and score <= majority:
        reasons.append("does_not_beat_majority_baseline")
    if candidate.get("leakage_warning"):
        reasons.append("leakage_warning")
    if candidate.get("has_action_labels"):
        reasons.append("action_label_boundary_violation")
    if isinstance(previous, (int, float)) and isinstance(score, (int, float)) and previous > score:
        reasons.append("diagnostic_only_not_superior_to_previous_direction")
    return reasons


def _select_for_slice(candidates: list[dict]) -> dict | None:
    eligible = []
    for candidate in candidates:
        reasons = _reject_reasons(candidate)
        if {"insufficient_validation_rows", "balanced_accuracy_unavailable", "does_not_beat_random_baseline", "leakage_warning", "action_label_boundary_violation"}.intersection(reasons):
            continue
        output = dict(candidate)
        output["champion_status"] = (
            "diagnostic_only_not_superior"
            if "diagnostic_only_not_superior_to_previous_direction" in reasons
            else "champion_candidate"
        )
        output["rejected_reasons"] = reasons
        eligible.append(output)
    if not eligible:
        return None
    eligible.sort(key=lambda item: (_score(item), _validation_rows(item)), reverse=True)
    return eligible[0]


def _slice(candidates: list[dict], fields: tuple[str, ...]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        key = "|".join(str(candidate.get(field) or "global") for field in fields)
        grouped[key].append(candidate)
    selected = {}
    for key, group in grouped.items():
        champion = _select_for_slice(group)
        if champion is not None:
            selected[key] = champion
    return dict(sorted(selected.items()))


def select_champions_by_slice(results: list[dict]) -> dict:
    """Select validation champions by global, horizon, ticker, and ticker/horizon slices."""

    candidates = [dict(item) for item in results if isinstance(item, dict)]
    rejected = []
    for candidate in candidates:
        reasons = _reject_reasons(candidate)
        if reasons:
            rejected.append({"candidate": _candidate_key(candidate), "reasons": reasons})
    global_champion = _select_for_slice(candidates)
    per_horizon = _slice(candidates, ("horizon",))
    per_ticker = _slice(candidates, ("ticker",))
    per_ticker_horizon = _slice(candidates, ("ticker", "horizon"))
    best = global_champion or (next(iter(per_horizon.values())) if per_horizon else None)
    return {
        "selection_status": "completed" if candidates else "not_ready_no_candidates",
        "candidate_count": len(candidates),
        "global_champion": global_champion,
        "per_horizon_champion": per_horizon,
        "per_ticker_champion": per_ticker,
        "per_ticker_horizon_champion": per_ticker_horizon,
        "rejected_candidates": rejected,
        "best_honest_pitchable_result": best,
        "beats_random_count": sum(1 for candidate in candidates if _score(candidate) > 0.5),
        "beats_majority_count": sum(
            1
            for candidate in candidates
            if isinstance((_baselines(candidate).get("majority_class_baseline_accuracy")), (int, float))
            and _score(candidate) > float(_baselines(candidate)["majority_class_baseline_accuracy"])
        ),
        "beats_previous_direction_count": sum(
            1
            for candidate in candidates
            if isinstance((_baselines(candidate).get("previous_direction_baseline_accuracy")), (int, float))
            and _score(candidate) > float(_baselines(candidate)["previous_direction_baseline_accuracy"])
        ),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_model_champion_report(result: dict) -> str:
    """Render compact champion selection results."""

    champion = result.get("global_champion") or {}
    metric = _metric(champion)
    lines = [
        "# Model Champion Selection",
        "",
        f"Selection status: {result.get('selection_status')}",
        f"Candidate count: {result.get('candidate_count')}",
        f"Beats random count: {result.get('beats_random_count')}",
        f"Beats majority count: {result.get('beats_majority_count')}",
        f"Beats previous-direction count: {result.get('beats_previous_direction_count')}",
        f"Global champion: {_candidate_key(champion) if champion else 'none'}",
        f"Global champion status: {champion.get('champion_status') if champion else 'none'}",
        f"Global champion balanced accuracy: {metric.get('balanced_accuracy') if metric else None}",
        "",
        "Boundary:",
        "Selection requires validation evidence and keeps rejected candidates with reasons.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select diagnostic model champions from a JSON result list.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = payload.get("model_results") if isinstance(payload, dict) else payload
    result = select_champions_by_slice(rows if isinstance(rows, list) else [])
    if args.format == "report":
        print(render_model_champion_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
