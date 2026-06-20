"""CLI summary for Quant Core slice selection and calibration gates."""

from __future__ import annotations

import argparse
import json

from src.hackaithon_mvp.forecast_actual_evaluation import load_forecast_actual_rows
from src.hackaithon_mvp.legacy_forecast_actual_adapter import (
    convert_legacy_rows_to_forecast_actual,
    load_legacy_rows,
)
from src.hackaithon_mvp.quant_core_calibration import (
    build_confidence_calibration_report,
    build_score_calibration_report,
)
from src.hackaithon_mvp.quant_core_calibration_gate import build_calibration_gate_policy
from src.hackaithon_mvp.quant_core_performance_attribution import (
    NON_CLAIM_TEXT,
    build_performance_attribution,
)


RECOMMENDED_QUANT_CORE_POLICY = {
    "use_slice_specific_selection": True,
    "use_abstention_for_weak_slices": True,
    "do_not_use_global_top_k_without_calibration": True,
    "require_walk_forward_validation_later": True,
}


def _load_rows(args: argparse.Namespace) -> tuple[dict, ...]:
    if args.legacy:
        legacy_rows = load_legacy_rows(args.input)
        return convert_legacy_rows_to_forecast_actual(
            legacy_rows,
            default_ticker=args.ticker,
            default_timeframe=args.timeframe,
            default_horizon_steps=args.horizon_steps,
            allow_row_index_timestamp=args.allow_row_index_timestamp,
            source_name=args.input,
        )
    return load_forecast_actual_rows(args.input)


def build_selector_summary(
    rows: tuple[dict, ...],
    *,
    min_sample_count: int = 30,
    bins: int = 10,
) -> dict:
    attribution = build_performance_attribution(rows, min_sample_count=min_sample_count)
    policy = build_calibration_gate_policy(attribution, min_sample_count=min_sample_count)
    score_report = build_score_calibration_report(rows, bins=bins)
    confidence_report = build_confidence_calibration_report(rows, bins=bins)
    global_metrics = attribution["global_metrics"]
    eligible_groups = [group for group in attribution["groups"] if group["is_directionally_eligible"]]
    return {
        "rows_total": attribution["rows_total"],
        "global_accuracy": global_metrics["directional_accuracy"],
        "global_balanced_accuracy": global_metrics["balanced_directional_accuracy"],
        "strong_group_count": len(attribution["strong_groups"]),
        "weak_group_count": len(attribution["weak_groups"]),
        "eligible_group_count": len(eligible_groups),
        "score_calibration": score_report,
        "confidence_calibration": confidence_report,
        "recommended_quant_core_policy": dict(RECOMMENDED_QUANT_CORE_POLICY),
        "calibration_gate_policy": {
            "eligible_group_count": policy["eligible_group_count"],
            "weak_group_count": policy["weak_group_count"],
            "strong_group_count": policy["strong_group_count"],
            "min_balanced_accuracy": policy["min_balanced_accuracy"],
            "min_sample_count": policy["min_sample_count"],
        },
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize local Quant Core performance attribution.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--horizon-steps", type=int, default=None)
    parser.add_argument("--allow-row-index-timestamp", action="store_true")
    parser.add_argument("--min-sample-count", type=int, default=30)
    parser.add_argument("--bins", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = _load_rows(args)
        summary = build_selector_summary(rows, min_sample_count=args.min_sample_count, bins=args.bins)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
