"""Plan the next honest forecast-edge sprint from local repository evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.clean_forecast_target_builder import build_clean_direction_targets
from src.hackaithon_mvp.local_training_dataset_builder import discover_local_ohlcv_sources, load_discovered_ohlcv_rows


PRIOR_FAILED_METRICS = {
    "accuracy_maximization_final_holdout_accuracy": 0.484890,
    "accuracy_maximization_final_holdout_balanced_accuracy": 0.479247,
    "beats_random": False,
    "beats_majority": False,
    "forecast_repair_strict_allowed_slices": 0,
    "forecast_repair_retained_coverage": 0.0,
    "forecast_repair_status": "forecast_mode_blocked_by_data_quality",
}
TARGET_HORIZONS = (1, 5, 10, 20)
AVOID_HORIZONS = (40,)
CLAIM_BOUNDARY = {
    "planning_only": True,
    "local_repo_inspection": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "post_hoc_repair_context": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast-edge plan is a local data and protocol readiness report, not an accuracy claim."


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _count_proxy_tickers(rows: list[dict]) -> dict[str, bool]:
    tickers = {str(row.get("ticker", "")).upper() for row in rows}
    return {
        "VN30": "VN30" in tickers,
        "VNINDEX": "VNINDEX" in tickers or "^VNINDEX" in tickers,
        "any_index_proxy": bool(tickers.intersection({"VN30", "VNINDEX", "^VNINDEX", "VNINDEX1"})),
    }


def _has_cross_sectional_panels(rows: list[dict]) -> bool:
    by_time: dict[str, set[str]] = {}
    for row in rows:
        by_time.setdefault(str(row.get("timestamp")), set()).add(str(row.get("ticker")))
    return any(len(tickers) >= 5 for tickers in by_time.values())


def _priority_horizons(clean_targets: dict) -> tuple[list[int], list[int]]:
    by_horizon = {int(key): int(value) for key, value in (clean_targets.get("rows_by_horizon") or {}).items()}
    recommended = [horizon for horizon in TARGET_HORIZONS if by_horizon.get(horizon, 0) >= 300]
    avoided = [horizon for horizon in AVOID_HORIZONS if by_horizon.get(horizon, 0) < 300]
    return recommended, avoided


def build_forecast_edge_plan(*, repo_root: str = ".") -> dict:
    """Inspect local data, prior failures, and feature/label gaps."""

    root = Path(repo_root).resolve()
    discovery = discover_local_ohlcv_sources(repo_root=str(root))
    bars = list(load_discovered_ohlcv_rows(repo_root=str(root)))
    clean_targets = build_clean_direction_targets(bars, horizons=TARGET_HORIZONS, non_overlapping=True)
    proxy = _count_proxy_tickers(bars)
    cross_sectional = _has_cross_sectional_panels(bars)
    recommended, avoided = _priority_horizons(clean_targets)
    repair_summary = _read_json(root / ".tmp_forecast_repair" / "forecast_repair_summary.json")
    data_gaps = []
    feature_gaps = []
    label_gaps = []
    if not bars:
        data_gaps.append("no_local_ohlcv_bars_discovered")
    if not proxy["any_index_proxy"]:
        data_gaps.append("no_local_market_index_proxy_detected")
    if not cross_sectional:
        data_gaps.append("insufficient_cross_sectional_timestamp_panels")
    if not recommended:
        label_gaps.append("fewer_than_300_clean_rows_for_priority_horizons")
    if avoided:
        label_gaps.append("h40_should_remain_optional_until_clean_row_count_and_stability_pass")
    feature_gaps.extend(
        [
            "current failed result needs richer market context and liquidity features",
            "previous-direction baseline dominance requires explicit leakage-risk handling",
        ]
    )
    return {
        "plan_status": "ready" if bars else "blocked_no_local_bars",
        "repo_root": str(root),
        "prior_failed_metrics": dict(PRIOR_FAILED_METRICS),
        "prior_repair_summary_detected": bool(repair_summary),
        "prior_repair_status": repair_summary.get("forecast_mode_status"),
        "local_ohlcv_discovery": {
            "candidate_file_count": discovery.get("candidate_file_count"),
            "preferred_file_count": discovery.get("preferred_file_count"),
            "ticker_count_estimate": discovery.get("ticker_count_estimate"),
        },
        "loaded_bar_rows": len(bars),
        "ticker_coverage": len({row.get("ticker") for row in bars}),
        "timestamp_panel_available": cross_sectional,
        "market_index_proxy_available": proxy,
        "clean_deoverlapped_target_rows": clean_targets.get("retained_rows"),
        "clean_rows_by_horizon": clean_targets.get("rows_by_horizon"),
        "enough_rows_for_priority_horizons": {
            f"h{horizon}": int((clean_targets.get("rows_by_horizon") or {}).get(str(horizon), 0)) >= 300
            for horizon in TARGET_HORIZONS
        },
        "recommended_target_horizons": recommended,
        "horizons_to_avoid": avoided,
        "required_row_counts": {
            "default_min_slice_rows": 300,
            "exploratory_min_slice_rows": 150,
            "minimum_holdout_rows_for_release_gate": 300,
        },
        "data_gaps": data_gaps,
        "feature_gaps": feature_gaps,
        "label_repair_gaps": label_gaps,
        "allowed_provider_data_expansion_plan": {
            "disabled_by_default": True,
            "requires_allow_provider_data_fetch_env": True,
            "required_env": ["DATA_PROVIDER", "MAX_TICKERS", "START_DATE", "END_DATE"],
            "write_root": ".tmp_forecast_edge",
        },
        "expected_impact_and_risk_notes": [
            "Clean targets reduce leakage and overlap risk but lower row coverage.",
            "Richer local features may help only if local bars contain real predictive structure.",
            "If strict holdout gates still reject every slice, the honest result is no robust edge on current local data.",
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_edge_plan_report(result: dict) -> str:
    """Render a compact forecast-edge plan."""

    lines = [
        "# Forecast Edge Planner",
        "",
        f"Plan status: {result.get('plan_status')}",
        f"Loaded bar rows: {result.get('loaded_bar_rows')}",
        f"Ticker coverage: {result.get('ticker_coverage')}",
        f"Clean target rows: {result.get('clean_deoverlapped_target_rows')}",
        f"Recommended horizons: {result.get('recommended_target_horizons')}",
        f"Horizons to avoid: {result.get('horizons_to_avoid')}",
        f"Market proxy available: {result.get('market_index_proxy_available')}",
        f"Cross-sectional panels available: {result.get('timestamp_panel_available')}",
        "",
        "Prior failed metrics:",
    ]
    prior = result.get("prior_failed_metrics") or {}
    lines.extend([f"- {key}: {value}" for key, value in prior.items()])
    lines.extend(["", "Data gaps:"])
    lines.extend([f"- {item}" for item in result.get("data_gaps") or []] or ["- none"])
    lines.extend(["", "Feature gaps:"])
    lines.extend([f"- {item}" for item in result.get("feature_gaps") or []] or ["- none"])
    lines.extend(["", "Label repair gaps:"])
    lines.extend([f"- {item}" for item in result.get("label_repair_gaps") or []] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "The previous final holdout was already inspected, so this is a repair plan with post-hoc context.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a local forecast-edge repair sprint.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_forecast_edge_plan(repo_root=args.repo_root)
    if args.format == "report":
        print(render_forecast_edge_plan_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
