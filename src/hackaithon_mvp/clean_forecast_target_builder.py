"""Build clean non-overlapping local forecast targets from OHLCV bars."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.local_training_dataset_builder import load_discovered_ohlcv_rows, normalize_ohlcv_rows


DEFAULT_HORIZONS = (1, 5, 10, 20)
OPTIONAL_HORIZONS = (40,)
CLAIM_BOUNDARY = {
    "local_bars_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_future_features": True,
    "non_overlapping_targets_supported": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Clean target builder computes local future directions only where valid future bars exist."


def _direction(value: float) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _group_by_ticker(rows: tuple[dict, ...]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row["ticker"])].append(row)
    for group_rows in groups.values():
        group_rows.sort(key=lambda item: str(item["timestamp"]))
    return dict(groups)


def _horizon_report(rows: list[dict]) -> dict[str, int]:
    counter = Counter(str(row.get("horizon")) for row in rows)
    return dict(sorted(counter.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 9999))


def build_clean_direction_targets(
    bars: list[dict],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    non_overlapping: bool = True,
) -> dict:
    """Create future-direction targets without duplicate keys or overlapping windows."""

    normalized = normalize_ohlcv_rows(bars)
    if not normalized:
        return {
            "target_status": "not_ready_no_valid_bars",
            "input_bar_rows": len(bars),
            "normalized_bar_rows": 0,
            "rows": [],
            "retained_rows": 0,
            "dropped_rows_missing_future_bar": 0,
            "dropped_duplicate_keys": 0,
            "dropped_overlapping_windows": 0,
            "rows_by_horizon": {},
            "rows_by_ticker_horizon": {},
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }

    clean_horizons = tuple(int(horizon) for horizon in horizons if int(horizon) > 0)
    rows: list[dict[str, Any]] = []
    dropped_missing_future = 0
    dropped_overlap = 0
    duplicate_keys = 0
    seen_keys: set[tuple[str, int, str]] = set()
    rows_by_ticker_horizon: dict[str, int] = {}

    for ticker, ticker_rows in _group_by_ticker(normalized).items():
        for horizon in clean_horizons:
            last_kept_index: int | None = None
            retained_for_slice = 0
            for index, row in enumerate(ticker_rows):
                future_index = index + horizon
                if future_index >= len(ticker_rows):
                    dropped_missing_future += 1
                    continue
                if non_overlapping and last_kept_index is not None and index - last_kept_index < horizon:
                    dropped_overlap += 1
                    continue
                future = ticker_rows[future_index]
                if str(future["timestamp"]) <= str(row["timestamp"]):
                    dropped_missing_future += 1
                    continue
                key = (ticker, horizon, str(row["timestamp"]))
                if key in seen_keys:
                    duplicate_keys += 1
                    continue
                seen_keys.add(key)
                close = float(row["close"])
                future_close = float(future["close"])
                if close == 0:
                    dropped_missing_future += 1
                    continue
                future_return = (future_close / close) - 1.0
                target = {
                    "ticker": ticker,
                    "horizon": horizon,
                    "timestamp": row["timestamp"],
                    "forecast_timestamp": row["timestamp"],
                    "actual_timestamp": future["timestamp"],
                    "future_timestamp": future["timestamp"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "future_close": future_close,
                    "future_return": future_return,
                    "actual_return": future_return,
                    "future_direction": _direction(future_return),
                    "actual_direction": _direction(future_return),
                    "non_overlapping_target": bool(non_overlapping),
                    "target_window_start_index": index,
                    "target_window_end_index": future_index,
                }
                rows.append(target)
                last_kept_index = index
                retained_for_slice += 1
            rows_by_ticker_horizon[f"{ticker}|h{horizon}"] = retained_for_slice

    rows.sort(key=lambda item: (str(item["ticker"]), int(item["horizon"]), str(item["timestamp"])))
    status = "ready" if rows else "not_ready_no_clean_targets"
    return {
        "target_status": status,
        "input_bar_rows": len(bars),
        "normalized_bar_rows": len(normalized),
        "requested_horizons": list(clean_horizons),
        "non_overlapping": bool(non_overlapping),
        "rows": rows,
        "retained_rows": len(rows),
        "dropped_rows_missing_future_bar": dropped_missing_future,
        "dropped_duplicate_keys": duplicate_keys,
        "dropped_overlapping_windows": dropped_overlap,
        "rows_by_horizon": _horizon_report(rows),
        "rows_by_ticker_horizon": dict(sorted(rows_by_ticker_horizon.items())),
        "optional_horizons": list(OPTIONAL_HORIZONS),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_clean_target_report(result: dict) -> str:
    """Render a compact clean-target report."""

    lines = [
        "# Clean Forecast Target Builder",
        "",
        f"Target status: {result.get('target_status')}",
        f"Input bar rows: {result.get('input_bar_rows')}",
        f"Normalized bar rows: {result.get('normalized_bar_rows')}",
        f"Retained target rows: {result.get('retained_rows')}",
        f"Dropped missing future bar rows: {result.get('dropped_rows_missing_future_bar')}",
        f"Dropped overlapping windows: {result.get('dropped_overlapping_windows')}",
        f"Dropped duplicate keys: {result.get('dropped_duplicate_keys')}",
        "",
        "Rows by horizon:",
    ]
    rows_by_horizon = result.get("rows_by_horizon") or {}
    lines.extend([f"- h{key}: {value}" for key, value in rows_by_horizon.items()] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Targets use future local closes only for labels, not features.",
            "Forecast timestamps are always earlier than actual timestamps.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build clean non-overlapping local forecast targets.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--horizons", default="1,5,10,20")
    parser.add_argument("--overlapping", action="store_true")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    bars = _load_jsonl(args.input) if args.input else list(load_discovered_ohlcv_rows(repo_root="."))
    horizons = tuple(int(item.strip()) for item in str(args.horizons).split(",") if item.strip())
    result = build_clean_direction_targets(bars, horizons=horizons, non_overlapping=not args.overlapping)
    if args.format == "report":
        print(render_clean_target_report({key: value for key, value in result.items() if key != "rows"}), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
