"""Build richer non-leaky local forecast features from OHLCV bars."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.local_training_dataset_builder import load_discovered_ohlcv_rows, normalize_ohlcv_rows


FEATURE_BLOCKS = (
    "market_context",
    "liquidity",
    "technical",
    "cross_sectional",
)
CLAIM_BOUNDARY = {
    "local_bars_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_future_features": True,
    "same_timestamp_cross_section_only": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Feature builder derives only local historical and same-timestamp context features."


def _safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def _rank_map(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 1.0}
    return {ticker: round(index / (len(ordered) - 1), 6) for index, (ticker, _) in enumerate(ordered)}


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _group_by_ticker(rows: tuple[dict, ...]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row["ticker"])].append(dict(row))
    for ticker_rows in groups.values():
        ticker_rows.sort(key=lambda item: str(item["timestamp"]))
    return dict(groups)


def _base_rows(rows: list[dict]) -> list[dict[str, Any]]:
    return [dict(row) for row in normalize_ohlcv_rows(rows)]


def _return_series(rows: list[dict]) -> dict[tuple[str, str], float | None]:
    out: dict[tuple[str, str], float | None] = {}
    for ticker, ticker_rows in _group_by_ticker(tuple(rows)).items():
        previous_close: float | None = None
        for row in ticker_rows:
            current_close = float(row["close"])
            out[(ticker, str(row["timestamp"]))] = None if previous_close in (None, 0) else (current_close / previous_close) - 1.0
            previous_close = current_close
    return out


def build_market_context_features(rows: list[dict]) -> dict:
    """Add same-timestamp market and excess-return features."""

    base = _base_rows(rows)
    returns = _return_series(base)
    by_time: dict[str, list[dict]] = defaultdict(list)
    for row in base:
        by_time[str(row["timestamp"])].append(row)
    proxy_tickers = {"VN30", "VNINDEX", "^VNINDEX", "VNINDEX1"}
    enriched = []
    for timestamp, timestamp_rows in sorted(by_time.items()):
        timestamp_returns = [
            float(returns[(str(row["ticker"]), timestamp)])
            for row in timestamp_rows
            if returns.get((str(row["ticker"]), timestamp)) is not None
        ]
        market_return = _mean(timestamp_returns)
        market_volatility = _std(timestamp_returns) or 0.0
        proxy_return = None
        for row in timestamp_rows:
            ticker = str(row["ticker"]).upper()
            if ticker in proxy_tickers and returns.get((ticker, timestamp)) is not None:
                proxy_return = returns[(ticker, timestamp)]
                break
        if proxy_return is None:
            proxy_return = market_return
        for row in timestamp_rows:
            ticker = str(row["ticker"])
            own_return = returns.get((ticker, timestamp))
            out = dict(row)
            out["feature_market_equal_weight_return"] = market_return or 0.0
            out["feature_market_volatility"] = market_volatility
            out["feature_market_proxy_return"] = proxy_return or 0.0
            out["feature_ticker_excess_return_vs_market"] = (own_return or 0.0) - (market_return or 0.0)
            enriched.append(out)
    return {
        "feature_status": "ready" if enriched else "not_ready_no_valid_bars",
        "feature_block": "market_context",
        "input_rows": len(rows),
        "row_count": len(enriched),
        "rows": sorted(enriched, key=lambda item: (str(item["ticker"]), str(item["timestamp"]))),
        "feature_columns": [
            "feature_market_equal_weight_return",
            "feature_market_proxy_return",
            "feature_market_volatility",
            "feature_ticker_excess_return_vs_market",
        ],
    }


def build_liquidity_features(rows: list[dict]) -> dict:
    """Add volume and turnover-derived historical liquidity features."""

    base = _base_rows(rows)
    enriched = []
    for ticker_rows in _group_by_ticker(tuple(base)).values():
        volumes: list[float] = []
        turnover_values: list[float] = []
        for row in ticker_rows:
            volume = float(row["volume"])
            close = float(row["close"])
            turnover = close * volume
            trailing_volumes = volumes[-20:]
            trailing_turnover = turnover_values[-20:]
            avg_volume = _mean(trailing_volumes)
            std_volume = _std(trailing_volumes)
            avg_turnover = _mean(trailing_turnover)
            out = dict(row)
            out["feature_volume_zscore"] = 0.0 if not std_volume else (volume - float(avg_volume or 0.0)) / std_volume
            out["feature_turnover_proxy"] = turnover
            out["feature_liquidity_shock"] = 0.0 if not avg_turnover else (turnover / avg_turnover) - 1.0
            enriched.append(out)
            volumes.append(volume)
            turnover_values.append(turnover)
    return {
        "feature_status": "ready" if enriched else "not_ready_no_valid_bars",
        "feature_block": "liquidity",
        "input_rows": len(rows),
        "row_count": len(enriched),
        "rows": enriched,
        "feature_columns": ["feature_volume_zscore", "feature_turnover_proxy", "feature_liquidity_shock"],
    }


def _ema(values: list[float], period: int) -> float | None:
    if not values:
        return None
    alpha = 2.0 / (period + 1.0)
    value = values[0]
    for item in values[1:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def _direction_from_return(value: float | None) -> int:
    if value is None:
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def build_technical_features(rows: list[dict]) -> dict:
    """Add historical price, volatility, and calendar features."""

    base = _base_rows(rows)
    enriched = []
    for ticker_rows in _group_by_ticker(tuple(base)).values():
        closes: list[float] = []
        returns: list[float] = []
        ranges: list[float] = []
        previous_return: float | None = None
        for row in ticker_rows:
            close = float(row["close"])
            high = float(row["high"])
            low = float(row["low"])
            rolling_returns = returns[-20:]
            rolling_closes = closes[-20:]
            gains = [value for value in rolling_returns[-14:] if value > 0]
            losses = [abs(value) for value in rolling_returns[-14:] if value < 0]
            avg_gain = _mean(gains) or 0.0
            avg_loss = _mean(losses) or 0.0
            denom = avg_gain + avg_loss
            rsi_like = 0.5 if denom == 0 else avg_gain / denom
            ema12 = _ema((closes + [close])[-26:], 12)
            ema26 = _ema((closes + [close])[-26:], 26)
            bollinger_mean = _mean((closes + [close])[-20:])
            bollinger_std = _std((closes + [close])[-20:])
            range_proxy = 0.0 if close == 0 else (high - low) / close
            range_window = ranges[-14:] + [range_proxy]
            realized_vol = _std(rolling_returns) or 0.0
            strength_base = rolling_closes[0] if rolling_closes else None
            relative_strength = 0.0 if not strength_base else (close / strength_base) - 1.0
            dt = _parse_dt(row.get("timestamp"))
            out = dict(row)
            out["feature_rolling_relative_strength"] = relative_strength
            out["feature_rsi_like"] = rsi_like
            out["feature_macd_like_momentum"] = (ema12 or close) - (ema26 or close)
            out["feature_bollinger_distance"] = 0.0 if not bollinger_std else (close - float(bollinger_mean or close)) / bollinger_std
            out["feature_atr_range_proxy"] = _mean(range_window) or range_proxy
            out["feature_realized_volatility_regime"] = realized_vol
            out["feature_trend_range_regime"] = abs(relative_strength) / (realized_vol + 1e-12)
            out["feature_day_of_week"] = float(dt.weekday()) if dt else 0.0
            out["feature_month_end"] = 1.0 if dt and dt.day >= 25 else 0.0
            out["feature_previous_realized_direction"] = float(_direction_from_return(previous_return))
            enriched.append(out)
            if closes and closes[-1] != 0:
                previous_return = (close / closes[-1]) - 1.0
                returns.append(previous_return)
            else:
                previous_return = None
            closes.append(close)
            ranges.append(range_proxy)
    feature_columns = [
        "feature_rolling_relative_strength",
        "feature_rsi_like",
        "feature_macd_like_momentum",
        "feature_bollinger_distance",
        "feature_atr_range_proxy",
        "feature_realized_volatility_regime",
        "feature_trend_range_regime",
        "feature_day_of_week",
        "feature_month_end",
        "feature_previous_realized_direction",
    ]
    return {
        "feature_status": "ready" if enriched else "not_ready_no_valid_bars",
        "feature_block": "technical",
        "input_rows": len(rows),
        "row_count": len(enriched),
        "rows": enriched,
        "feature_columns": feature_columns,
    }


def build_cross_sectional_features(rows: list[dict]) -> dict:
    """Add same-timestamp rank features across local tickers."""

    base = _base_rows(rows)
    returns = _return_series(base)
    by_time: dict[str, list[dict]] = defaultdict(list)
    for row in base:
        by_time[str(row["timestamp"])].append(row)
    enriched = []
    for timestamp, timestamp_rows in sorted(by_time.items()):
        return_values = {
            str(row["ticker"]): float(returns[(str(row["ticker"]), timestamp)])
            for row in timestamp_rows
            if returns.get((str(row["ticker"]), timestamp)) is not None
        }
        volume_values = {str(row["ticker"]): float(row["volume"]) for row in timestamp_rows}
        return_ranks = _rank_map(return_values)
        volume_ranks = _rank_map(volume_values)
        for row in timestamp_rows:
            ticker = str(row["ticker"])
            out = dict(row)
            out["feature_cross_sectional_return_rank"] = return_ranks.get(ticker, 0.5)
            out["feature_cross_sectional_volume_rank"] = volume_ranks.get(ticker, 0.5)
            enriched.append(out)
    return {
        "feature_status": "ready" if enriched else "not_ready_no_valid_bars",
        "feature_block": "cross_sectional",
        "input_rows": len(rows),
        "row_count": len(enriched),
        "rows": sorted(enriched, key=lambda item: (str(item["ticker"]), str(item["timestamp"]))),
        "feature_columns": ["feature_cross_sectional_return_rank", "feature_cross_sectional_volume_rank"],
    }


def build_forecast_edge_features(rows: list[dict]) -> dict:
    """Build all forecast-edge feature blocks and merge them by ticker/timestamp."""

    base = _base_rows(rows)
    merged: dict[tuple[str, str], dict[str, Any]] = {
        (str(row["ticker"]), str(row["timestamp"])): dict(row) for row in base
    }
    block_results = [
        build_market_context_features(rows),
        build_liquidity_features(rows),
        build_technical_features(rows),
        build_cross_sectional_features(rows),
    ]
    feature_columns: set[str] = set()
    for block in block_results:
        for column in block.get("feature_columns") or []:
            if column.startswith("feature_") and "future" not in column and "target" not in column:
                feature_columns.add(str(column))
        for row in block.get("rows") or []:
            key = (str(row.get("ticker")), str(row.get("timestamp")))
            target = merged.setdefault(key, {"ticker": key[0], "timestamp": key[1]})
            for column in block.get("feature_columns") or []:
                if column in row:
                    target[column] = row[column]
    output_rows = sorted(merged.values(), key=lambda item: (str(item.get("ticker")), str(item.get("timestamp"))))
    return {
        "feature_status": "ready" if output_rows else "not_ready_no_valid_bars",
        "input_rows": len(rows),
        "normalized_rows": len(base),
        "row_count": len(output_rows),
        "feature_blocks": list(FEATURE_BLOCKS),
        "feature_columns": sorted(feature_columns),
        "rows": output_rows,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_edge_feature_report(result: dict) -> str:
    """Render a compact feature-building report."""

    lines = [
        "# Forecast Edge Feature Builder",
        "",
        f"Feature status: {result.get('feature_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Normalized rows: {result.get('normalized_rows')}",
        f"Feature rows: {result.get('row_count')}",
        f"Feature blocks: {', '.join(result.get('feature_blocks') or [])}",
        f"Feature columns: {len(result.get('feature_columns') or [])}",
        "",
        "Boundary:",
        "Rolling features end at or before the forecast timestamp.",
        "Cross-sectional ranks use same-timestamp local panels only.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build non-leaky forecast-edge features from local OHLCV bars.")
    parser.add_argument("--input", default=None)
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
    rows = _load_jsonl(args.input) if args.input else list(load_discovered_ohlcv_rows(repo_root="."))
    result = build_forecast_edge_features(rows)
    if args.format == "report":
        print(render_forecast_edge_feature_report({key: value for key, value in result.items() if key != "rows"}), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
