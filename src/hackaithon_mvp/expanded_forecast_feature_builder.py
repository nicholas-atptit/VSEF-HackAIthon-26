"""Expanded non-leaky forecast features for local price panels."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.data_expanded_forecast_contract import load_expanded_price_panel
from src.hackaithon_mvp.local_training_dataset_builder import load_discovered_ohlcv_rows


FEATURE_BLOCKS = (
    "returns",
    "market_context",
    "sector_context",
    "risk_liquidity",
    "technical",
    "calendar",
)
CLAIM_BOUNDARY = {
    "local_rows_only": True,
    "no_future_features": True,
    "no_target_columns_as_features": True,
    "same_timestamp_cross_section_only": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Expanded feature builder uses only local historical and same-timestamp information."


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


def _covariance(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) < 2 or len(x_values) != len(y_values):
        return None
    x_avg = sum(x_values) / len(x_values)
    y_avg = sum(y_values) / len(y_values)
    return sum((x - x_avg) * (y - y_avg) for x, y in zip(x_values, y_values)) / (len(x_values) - 1)


def _correlation(x_values: list[float], y_values: list[float]) -> float:
    cov = _covariance(x_values, y_values)
    x_std = _std(x_values)
    y_std = _std(y_values)
    if cov is None or not x_std or not y_std:
        return 0.0
    return cov / (x_std * y_std)


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
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_panel_rows(rows: list[dict]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        timestamp = str(row.get("timestamp") or row.get("date") or row.get("datetime") or "").strip()
        open_value = _safe_float(row.get("open", row.get("o")))
        high_value = _safe_float(row.get("high", row.get("h")))
        low_value = _safe_float(row.get("low", row.get("l")))
        close_value = _safe_float(row.get("close", row.get("c")))
        volume_value = _safe_float(row.get("volume", row.get("v")))
        if not ticker or not timestamp or None in (open_value, high_value, low_value, close_value, volume_value):
            continue
        item = {
            "ticker": ticker,
            "timestamp": timestamp,
            "open": float(open_value),
            "high": float(high_value),
            "low": float(low_value),
            "close": float(close_value),
            "volume": float(volume_value),
        }
        for key in (
            "adjusted_close",
            "vwap",
            "turnover",
            "market_cap",
            "foreign_buy",
            "foreign_sell",
            "foreign_net",
            "sector",
            "industry",
            "index_vnindex_close",
            "index_vn30_close",
            "index_return",
            "sector_return",
            "news_score",
            "event_flag",
        ):
            if key in row and row[key] not in (None, ""):
                item[key] = row[key]
        output.append(item)
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in output:
        dedup[(row["ticker"], row["timestamp"])] = row
    return sorted(dedup.values(), key=lambda item: (item["ticker"], item["timestamp"]))


def _group_by_ticker(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row["ticker"])].append(dict(row))
    for group_rows in groups.values():
        group_rows.sort(key=lambda item: str(item["timestamp"]))
    return dict(groups)


def _direction(value: float | None) -> float:
    if value is None:
        return 0.0
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def _ema(values: list[float], period: int) -> float | None:
    if not values:
        return None
    alpha = 2.0 / (period + 1.0)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


def build_expanded_forecast_features(rows: list[dict]) -> dict:
    """Build non-leaky expanded features from local panel rows."""

    base = _normalize_panel_rows(rows)
    if not base:
        return {
            "feature_status": "not_ready_no_valid_rows",
            "input_rows": len(rows),
            "normalized_rows": 0,
            "rows": [],
            "feature_columns": [],
            "feature_blocks": list(FEATURE_BLOCKS),
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }

    by_time: dict[str, list[dict]] = defaultdict(list)
    for row in base:
        by_time[str(row["timestamp"])].append(row)

    market_return_by_time: dict[str, float] = {}
    sector_return_by_time: dict[tuple[str, str], float] = {}
    ticker_returns: dict[tuple[str, str], float | None] = {}
    adjusted_returns: dict[tuple[str, str], float | None] = {}
    for ticker, ticker_rows in _group_by_ticker(base).items():
        previous_close: float | None = None
        previous_adjusted: float | None = None
        for row in ticker_rows:
            close = float(row["close"])
            adjusted = _safe_float(row.get("adjusted_close"))
            timestamp = str(row["timestamp"])
            ticker_returns[(ticker, timestamp)] = None if previous_close in (None, 0) else (close / previous_close) - 1.0
            adjusted_returns[(ticker, timestamp)] = (
                None if adjusted is None or previous_adjusted in (None, 0) else (adjusted / previous_adjusted) - 1.0
            )
            previous_close = close
            if adjusted is not None:
                previous_adjusted = adjusted

    for timestamp, timestamp_rows in by_time.items():
        explicit_returns = [_safe_float(row.get("index_return")) for row in timestamp_rows if _safe_float(row.get("index_return")) is not None]
        if explicit_returns:
            market_return_by_time[timestamp] = float(_mean(explicit_returns) or 0.0)
        else:
            returns = [ticker_returns[(str(row["ticker"]), timestamp)] for row in timestamp_rows]
            market_return_by_time[timestamp] = float(_mean([value for value in returns if value is not None]) or 0.0)
        sector_groups: dict[str, list[float]] = defaultdict(list)
        for row in timestamp_rows:
            sector = str(row.get("sector") or row.get("industry") or "unspecified")
            explicit = _safe_float(row.get("sector_return"))
            own = ticker_returns.get((str(row["ticker"]), timestamp))
            if explicit is not None:
                sector_groups[sector].append(explicit)
            elif own is not None:
                sector_groups[sector].append(own)
        for sector, values in sector_groups.items():
            sector_return_by_time[(timestamp, sector)] = float(_mean(values) or 0.0)

    enriched: list[dict[str, Any]] = []
    for ticker, ticker_rows in _group_by_ticker(base).items():
        trailing_returns: list[float] = []
        trailing_market_returns: list[float] = []
        trailing_volume: list[float] = []
        trailing_turnover: list[float] = []
        trailing_foreign_net: list[float] = []
        trailing_closes: list[float] = []
        trailing_ranges: list[float] = []
        previous_realized_return: float | None = None
        for row in ticker_rows:
            timestamp = str(row["timestamp"])
            close = float(row["close"])
            high = float(row["high"])
            low = float(row["low"])
            volume = float(row["volume"])
            own_return = ticker_returns.get((ticker, timestamp))
            adjusted_return = adjusted_returns.get((ticker, timestamp))
            market_return = market_return_by_time.get(timestamp, 0.0)
            sector = str(row.get("sector") or row.get("industry") or "unspecified")
            sector_return = sector_return_by_time.get((timestamp, sector), market_return)
            returns_window = trailing_returns[-20:]
            market_window = trailing_market_returns[-20:]
            paired_len = min(len(returns_window), len(market_window))
            paired_returns = returns_window[-paired_len:] if paired_len else []
            paired_market = market_window[-paired_len:] if paired_len else []
            market_var = _std(paired_market)
            covariance = _covariance(paired_returns, paired_market)
            beta = 0.0 if covariance is None or not market_var else covariance / (market_var * market_var)
            correlation = _correlation(paired_returns, paired_market)
            volume_std = _std(trailing_volume[-20:])
            volume_avg = _mean(trailing_volume[-20:])
            turnover_value = _safe_float(row.get("turnover"))
            if turnover_value is None:
                turnover_value = close * volume
            turnover_std = _std(trailing_turnover[-20:])
            turnover_avg = _mean(trailing_turnover[-20:])
            foreign_net = _safe_float(row.get("foreign_net"))
            if foreign_net is None:
                foreign_buy = _safe_float(row.get("foreign_buy"))
                foreign_sell = _safe_float(row.get("foreign_sell"))
                foreign_net = None if foreign_buy is None or foreign_sell is None else foreign_buy - foreign_sell
            foreign_std = _std(trailing_foreign_net[-20:])
            foreign_avg = _mean(trailing_foreign_net[-20:])
            gains = [value for value in trailing_returns[-14:] if value > 0]
            losses = [abs(value) for value in trailing_returns[-14:] if value < 0]
            avg_gain = _mean(gains) or 0.0
            avg_loss = _mean(losses) or 0.0
            rsi_like = 0.5 if avg_gain + avg_loss == 0 else avg_gain / (avg_gain + avg_loss)
            closes_with_current = trailing_closes + [close]
            ema12 = _ema(closes_with_current[-26:], 12)
            ema26 = _ema(closes_with_current[-26:], 26)
            close_mean = _mean(closes_with_current[-20:])
            close_std = _std(closes_with_current[-20:])
            range_proxy = 0.0 if close == 0 else (high - low) / close
            dt = _parse_dt(timestamp)
            return_ranks = _rank_map(
                {
                    str(member["ticker"]): ticker_returns.get((str(member["ticker"]), timestamp)) or 0.0
                    for member in by_time.get(timestamp, [])
                }
            )
            volume_ranks = _rank_map({str(member["ticker"]): float(member["volume"]) for member in by_time.get(timestamp, [])})
            out = dict(row)
            out["feature_ticker_return"] = own_return or 0.0
            out["feature_adjusted_return"] = adjusted_return or 0.0
            out["feature_index_return"] = market_return
            out["feature_ticker_excess_return_over_index"] = (own_return or 0.0) - market_return
            out["feature_sector_excess_return"] = (own_return or 0.0) - sector_return
            out["feature_rolling_beta_to_index"] = beta
            out["feature_rolling_correlation_to_index"] = correlation
            out["feature_rolling_volatility"] = _std(returns_window) or 0.0
            out["feature_volume_zscore"] = 0.0 if not volume_std else (volume - float(volume_avg or 0.0)) / volume_std
            out["feature_turnover_zscore"] = 0.0 if not turnover_std else (turnover_value - float(turnover_avg or 0.0)) / turnover_std
            out["feature_foreign_net_flow_zscore"] = (
                0.0 if foreign_net is None or not foreign_std else (foreign_net - float(foreign_avg or 0.0)) / foreign_std
            )
            out["feature_liquidity_shock"] = 0.0 if not turnover_avg else (turnover_value / turnover_avg) - 1.0
            out["feature_rsi_like"] = rsi_like
            out["feature_macd_like_momentum"] = (ema12 or close) - (ema26 or close)
            out["feature_bollinger_distance"] = 0.0 if not close_std else (close - float(close_mean or close)) / close_std
            out["feature_atr_proxy"] = _mean(trailing_ranges[-14:] + [range_proxy]) or range_proxy
            out["feature_market_regime"] = 1.0 if market_return > 0 else -1.0 if market_return < 0 else 0.0
            out["feature_sector_regime"] = 1.0 if sector_return > 0 else -1.0 if sector_return < 0 else 0.0
            out["feature_day_of_week"] = float(dt.weekday()) if dt else 0.0
            out["feature_month_end"] = 1.0 if dt and dt.day >= 25 else 0.0
            out["feature_prior_realized_direction"] = _direction(previous_realized_return)
            out["feature_cross_sectional_return_rank"] = return_ranks.get(ticker, 0.5)
            out["feature_cross_sectional_volume_rank"] = volume_ranks.get(ticker, 0.5)
            enriched.append(out)
            if own_return is not None:
                trailing_returns.append(own_return)
                previous_realized_return = own_return
            else:
                previous_realized_return = None
            trailing_market_returns.append(market_return)
            trailing_volume.append(volume)
            trailing_turnover.append(turnover_value)
            if foreign_net is not None:
                trailing_foreign_net.append(foreign_net)
            trailing_closes.append(close)
            trailing_ranges.append(range_proxy)

    feature_columns = sorted(
        key
        for row in enriched
        for key in row
        if key.startswith("feature_") and "future" not in key.lower() and "target" not in key.lower() and "actual" not in key.lower()
    )
    feature_columns = sorted(set(feature_columns))
    return {
        "feature_status": "ready" if enriched else "not_ready_no_valid_rows",
        "input_rows": len(rows),
        "normalized_rows": len(base),
        "row_count": len(enriched),
        "feature_blocks": list(FEATURE_BLOCKS),
        "feature_columns": feature_columns,
        "rows": sorted(enriched, key=lambda item: (str(item["ticker"]), str(item["timestamp"]))),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_expanded_forecast_feature_report(result: dict) -> str:
    """Render expanded feature summary."""

    lines = [
        "# Expanded Forecast Feature Builder",
        "",
        f"Feature status: {result.get('feature_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Normalized rows: {result.get('normalized_rows')}",
        f"Feature rows: {result.get('row_count')}",
        f"Feature blocks: {result.get('feature_blocks')}",
        f"Feature columns: {len(result.get('feature_columns') or [])}",
        "",
        "Boundary:",
        "Rolling windows end at or before the forecast timestamp.",
        "Target, actual, and future columns are not emitted as feature columns.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build expanded non-leaky forecast features.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_expanded_price_panel(args.input) if args.input else list(load_discovered_ohlcv_rows(repo_root="."))
    result = build_expanded_forecast_features(rows)
    public = {key: value for key, value in result.items() if key != "rows"}
    if args.format == "report":
        print(render_expanded_forecast_feature_report(public), end="")
    else:
        print(json.dumps(public, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
