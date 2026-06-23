"""Plan a bounded local accuracy maximization run."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.full_eligible_model_trainer import discover_trainable_model_specs
from src.hackaithon_mvp.local_training_dataset_builder import (
    FEATURE_BLOCKS,
    build_supervised_direction_dataset,
    discover_local_ohlcv_sources,
    load_discovered_ohlcv_rows,
)


CLAIM_BOUNDARY = {
    "planner_only": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_model_update": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Accuracy maximization planner inspects local readiness only; execution requires an explicit temp output root."


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _class_balance(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        key = f"{row.get('ticker')}|h{row.get('horizon')}"
        grouped[key][str(row.get("future_direction"))] += 1
    output = {}
    for key, counter in grouped.items():
        total = sum(counter.values())
        majority = max(counter.values()) if counter else 0
        output[key] = {
            "row_count": total,
            "up": counter.get("up", 0),
            "down": counter.get("down", 0),
            "flat": counter.get("flat", 0),
            "majority_ratio": round(majority / total, 6) if total else None,
        }
    return dict(sorted(output.items()))


def _best_and_weak_slices(previous: dict) -> tuple[list[dict], list[dict]]:
    accuracy = previous.get("final_accuracy") or {}
    groups = (accuracy.get("accuracy_evaluation") or {}).get("groups") or {}
    candidates = []
    for section_name in ("by_horizon", "by_ticker", "by_ticker_horizon"):
        for key, value in (groups.get(section_name) or {}).items():
            directional = value.get("directional") or {}
            bacc = directional.get("balanced_accuracy")
            if isinstance(bacc, (int, float)):
                candidates.append(
                    {
                        "slice_type": section_name,
                        "slice": key,
                        "balanced_accuracy": bacc,
                        "accuracy": directional.get("accuracy"),
                        "rows": directional.get("coverage_count"),
                    }
                )
    best = sorted(candidates, key=lambda item: (item["balanced_accuracy"], item.get("rows") or 0), reverse=True)[:10]
    weak = sorted(candidates, key=lambda item: (item["balanced_accuracy"], -(item.get("rows") or 0)))[:10]
    return best, weak


def _recommended_horizons(dataset_rows: list[dict], previous: dict) -> tuple[list[str], list[str]]:
    horizon_counts = Counter(str(row.get("horizon")) for row in dataset_rows)
    previous_accuracy = previous.get("final_accuracy") or {}
    by_horizon = ((previous_accuracy.get("accuracy_evaluation") or {}).get("groups") or {}).get("by_horizon") or {}
    scored = []
    for key, value in by_horizon.items():
        horizon = key.split("=")[-1]
        directional = value.get("directional") or {}
        bacc = directional.get("balanced_accuracy")
        if isinstance(bacc, (int, float)):
            scored.append((horizon, float(bacc), int(directional.get("coverage_count") or 0)))
    if scored:
        scored.sort(key=lambda item: (item[1], item[2]), reverse=True)
        recommended = [f"h{item[0]}" for item in scored[:3]]
        abstain = [f"h{item[0]}" for item in scored if item[1] < 0.50]
        return recommended, abstain[:5]
    common = [f"h{horizon}" for horizon, _ in horizon_counts.most_common(3)]
    sparse = [f"h{horizon}" for horizon, count in horizon_counts.items() if count < 100]
    return common, sparse


def build_accuracy_maximization_plan(*, repo_root: str = ".") -> dict:
    """Inspect local inputs and recommend a bounded accuracy maximization run."""

    root = Path(repo_root).resolve()
    discovery = discover_local_ohlcv_sources(repo_root=str(root))
    bars = list(load_discovered_ohlcv_rows(repo_root=str(root)))
    dataset = build_supervised_direction_dataset(bars, feature_blocks=FEATURE_BLOCKS)
    dataset_rows = dataset.get("rows", [])
    trainable = discover_trainable_model_specs()
    previous = _read_json(root / ".tmp_performance_rescue" / "performance_rescue_summary.json")
    prior_accuracy = previous.get("final_accuracy_summary") or {}
    best_slices, weak_slices = _best_and_weak_slices(previous)
    recommended_horizons, abstain_horizons = _recommended_horizons(dataset_rows, previous)
    rows_by_ticker = Counter(str(row.get("ticker")) for row in dataset_rows)
    recommended_tickers = [ticker for ticker, count in rows_by_ticker.most_common(12) if count >= 500]
    abstain_tickers = [ticker for ticker, count in rows_by_ticker.items() if count < 250]
    leakage_warnings = []
    baseline = (previous.get("baseline_sanity_audit") or {}).get("previous_direction_baseline") or {}
    signal = previous.get("signal_sanity_audit") or {}
    if baseline.get("leakage_warning"):
        leakage_warnings.append("previous_direction_baseline_leakage_warning")
    if baseline.get("overlap_warning"):
        leakage_warnings.append("overlapping_horizon_labels_require_purge")
    if ((signal.get("prediction_flip_rescue") or {}).get("possible_label_polarity_mismatch")):
        leakage_warnings.append("label_polarity_mismatch_requires_fixed_validation_policy")
    return {
        "planner_status": "ready" if dataset_rows else "blocked_no_supervised_rows",
        "repo_root": str(root),
        "available_ohlcv_rows": len(bars),
        "ohlcv_candidate_files": discovery.get("candidate_file_count"),
        "supervised_dataset_rows": len(dataset_rows),
        "ticker_coverage": dict(sorted(rows_by_ticker.items())),
        "horizon_coverage": dict(sorted(Counter(str(row.get("horizon")) for row in dataset_rows).items())),
        "class_imbalance_by_ticker_horizon": _class_balance(dataset_rows),
        "previous_rescue_found": bool(previous),
        "previous_rescue_summary": prior_accuracy,
        "best_current_slices": best_slices,
        "weak_slices": weak_slices,
        "recommended_horizons_to_prioritize": recommended_horizons,
        "recommended_tickers_to_prioritize": recommended_tickers,
        "horizons_to_abstain_or_downweight": abstain_horizons,
        "tickers_to_abstain_or_downweight": sorted(abstain_tickers),
        "candidate_feature_blocks": list(FEATURE_BLOCKS),
        "candidate_model_families": sorted({spec.get("model_family") for spec in trainable.get("trainable_model_specs", [])}),
        "candidate_model_keys": trainable.get("supported_model_keys"),
        "candidate_ensemble_methods": [
            "majority_vote",
            "probability_average",
            "weighted_probability_average",
            "per_ticker_champion",
            "per_horizon_champion",
            "per_ticker_horizon_champion",
            "confidence_gated_champion_ensemble",
        ],
        "leakage_or_audit_warnings": leakage_warnings,
        "expected_runtime_class": "medium" if len(dataset_rows) < 250_000 else "large",
        "max_safe_run_plan": {
            "output_root": ".tmp_accuracy_maximization",
            "max_workers": 1,
            "max_models": 300,
            "max_runtime_minutes": 90,
            "use_purged_validation": True,
            "final_holdout_fraction": 0.20,
            "no_external_data": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_accuracy_maximization_plan_report(result: dict) -> str:
    """Render compact accuracy maximization planning output."""

    lines = [
        "# Accuracy Maximization Planner",
        "",
        f"Planner status: {result.get('planner_status')}",
        f"Available OHLCV rows: {result.get('available_ohlcv_rows')}",
        f"Supervised dataset rows: {result.get('supervised_dataset_rows')}",
        f"Ticker count: {len(result.get('ticker_coverage') or {})}",
        f"Horizon coverage: {result.get('horizon_coverage')}",
        f"Previous rescue found: {result.get('previous_rescue_found')}",
        f"Recommended horizons: {result.get('recommended_horizons_to_prioritize')}",
        f"Recommended tickers: {result.get('recommended_tickers_to_prioritize')}",
        f"Horizons to abstain/downweight: {result.get('horizons_to_abstain_or_downweight')}",
        f"Expected runtime class: {result.get('expected_runtime_class')}",
        "",
        "Audit warnings:",
        *([f"- {item}" for item in result.get("leakage_or_audit_warnings", [])] or ["- none"]),
        "",
        "Candidate feature blocks:",
        f"- {', '.join(result.get('candidate_feature_blocks') or [])}",
        "",
        "Boundary:",
        "This is a no-write local planning step; execution requires an explicit temp root.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a bounded local accuracy maximization run.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_accuracy_maximization_plan(repo_root=args.repo_root)
    if args.format == "report":
        print(render_accuracy_maximization_plan_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
