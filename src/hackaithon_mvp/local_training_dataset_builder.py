"""Build local supervised direction datasets from OHLCV bars."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BAR_SUFFIXES = {".csv", ".jsonl", ".json"}
HORIZONS = (1, 5, 10, 20, 40)
REQUIRED_BAR_FIELDS = {"open", "high", "low", "close", "volume"}
TIME_ALIASES = ("datetime", "timestamp", "date")
TICKER_ALIASES = ("ticker", "symbol", "index_code")
MAX_DISCOVERY_FILES = 500
MAX_SOURCE_BYTES = 20_000_000
MAX_DEFAULT_SOURCE_FILES = 40
MIN_ROWS_PER_TICKER = 80
EXCLUDED_DIR_NAMES = {".git", ".venv", "__pycache__", ".pytest_cache", ".pytest-tmp", "node_modules", "configs", "secrets"}
EXCLUDED_PREFIXES = (".tmp_", ".pytest-tmp")
PREFERRED_SOURCE_MARKERS = (
    "paper_evidence_raw_full_export/raw_data/data/market_cache/vnstock_data/vn30/daily_2015",
    "paper_evidence_raw_full_export/raw_data/data/market_cache/vnstock_data/indices/daily_2015",
)
CLAIM_BOUNDARY = {
    "local_ohlcv_only": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_future_leakage": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local supervised dataset builder only; targets use future local bars where available."


def _norm_path_text(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


def _should_skip_dir(dirname: str) -> bool:
    lowered = dirname.lower()
    return lowered in EXCLUDED_DIR_NAMES or any(lowered.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def _is_preferred_bar_path(path: Path) -> bool:
    text = _norm_path_text(path)
    return any(marker in text for marker in PREFERRED_SOURCE_MARKERS)


def _safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    lowered = {str(key).lower(): key for key in row}
    for alias in aliases:
        key = lowered.get(alias)
        if key is not None and row[key] not in (None, ""):
            return row[key]
    return None


def _parse_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return text if text else None


def _csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def _looks_like_ohlcv(path: Path) -> bool:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES or path.suffix.lower() not in BAR_SUFFIXES:
            return False
        if path.suffix.lower() == ".csv":
            fields = {field.lower() for field in _csv_header(path)}
        elif path.suffix.lower() == ".jsonl":
            fields: set[str] = set()
            with path.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    if line.strip():
                        row = json.loads(line)
                        if isinstance(row, dict):
                            fields = {str(key).lower() for key in row}
                        break
        else:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = payload.get("rows") if isinstance(payload, dict) else payload
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                fields = {str(key).lower() for key in rows[0]}
            elif isinstance(payload, dict):
                fields = {str(key).lower() for key in payload}
            else:
                fields = set()
    except (OSError, UnicodeDecodeError, csv.Error, json.JSONDecodeError):
        return False
    has_bar_fields = REQUIRED_BAR_FIELDS.issubset(fields) or {"o", "h", "l", "c", "v"}.issubset(fields)
    has_identity = bool(fields.intersection(TICKER_ALIASES)) or "index_code" in fields
    has_time = bool(fields.intersection(TIME_ALIASES))
    return has_bar_fields and has_identity and has_time


def _candidate_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    walked_dirs = 0
    for dirpath, dirnames, filenames in os.walk(root):
        walked_dirs += 1
        dirnames[:] = [dirname for dirname in dirnames if not _should_skip_dir(dirname)]
        if walked_dirs > 5_000:
            break
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in BAR_SUFFIXES:
                continue
            if _looks_like_ohlcv(path):
                paths.append(path)
                if len(paths) >= MAX_DISCOVERY_FILES:
                    break
        if len(paths) >= MAX_DISCOVERY_FILES:
            break
    preferred = [path for path in paths if _is_preferred_bar_path(path)]
    others = [path for path in paths if path not in set(preferred)]
    return tuple(sorted(preferred, key=str) + sorted(others, key=str))


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def discover_local_ohlcv_sources(*, repo_root: str = ".") -> dict:
    """Discover local OHLCV files without reading large datasets into memory."""

    root = Path(repo_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo_root not found: {repo_root}")
    candidates = []
    for path in _candidate_paths(root):
        try:
            header = _csv_header(path) if path.suffix.lower() == ".csv" else []
            size = path.stat().st_size
        except OSError:
            header = []
            size = 0
        candidates.append(
            {
                "path": _relative(path, root),
                "bytes": size,
                "preferred_source": _is_preferred_bar_path(path),
                "schema_guess": header,
            }
        )
    tickers = sorted({Path(item["path"]).stem.upper() for item in candidates if item["preferred_source"]})
    return {
        "discovery_status": "completed",
        "candidate_file_count": len(candidates),
        "preferred_file_count": len([item for item in candidates if item["preferred_source"]]),
        "candidate_files": candidates,
        "ticker_count_estimate": len(tickers),
        "tickers_estimate": tickers,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _normalize_bar(row: dict[str, Any]) -> dict[str, Any] | None:
    timestamp = _parse_timestamp(_first_value(row, TIME_ALIASES))
    ticker_value = _first_value(row, TICKER_ALIASES)
    ticker = str(ticker_value).strip().upper() if ticker_value not in (None, "") else ""
    open_value = _safe_float(row.get("open", row.get("o")))
    high_value = _safe_float(row.get("high", row.get("h")))
    low_value = _safe_float(row.get("low", row.get("l")))
    close_value = _safe_float(row.get("close", row.get("c")))
    volume_value = _safe_float(row.get("volume", row.get("v")))
    if not timestamp or not ticker or None in (open_value, high_value, low_value, close_value, volume_value):
        return None
    if high_value < low_value or volume_value < 0:
        return None
    return {
        "timestamp": timestamp,
        "ticker": ticker,
        "open": float(open_value),
        "high": float(high_value),
        "low": float(low_value),
        "close": float(close_value),
        "volume": float(volume_value),
        "source_frequency": str(row.get("frequency") or ""),
    }


def normalize_ohlcv_rows(rows: list[dict]) -> tuple[dict, ...]:
    """Normalize OHLCV aliases and drop invalid rows."""

    normalized = [_normalize_bar(row) for row in rows if isinstance(row, dict)]
    clean = [row for row in normalized if row is not None]
    dedup: dict[tuple[str, str], dict] = {}
    for row in clean:
        dedup[(row["ticker"], row["timestamp"])] = row
    return tuple(sorted(dedup.values(), key=lambda row: (row["ticker"], row["timestamp"])))


def _load_rows_from_file(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        rows = []
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if line.strip():
                    item = json.loads(line)
                    if isinstance(item, dict):
                        rows.append(item)
        return rows
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


def load_discovered_ohlcv_rows(*, repo_root: str = ".", max_tickers: int | None = None) -> tuple[dict, ...]:
    """Load preferred local OHLCV rows for the full-run pipeline."""

    root = Path(repo_root).resolve()
    discovery = discover_local_ohlcv_sources(repo_root=str(root))
    preferred = [item for item in discovery["candidate_files"] if item["preferred_source"]]
    if not preferred:
        preferred = discovery["candidate_files"]
    selected: list[dict[str, Any]] = []
    tickers_seen: set[str] = set()
    for item in preferred:
        path = root / item["path"]
        ticker = path.stem.upper()
        if max_tickers is not None and ticker not in tickers_seen and len(tickers_seen) >= max_tickers:
            continue
        rows = _load_rows_from_file(path)
        selected.extend(rows)
        tickers_seen.add(ticker)
        if len(tickers_seen) >= (max_tickers or MAX_DEFAULT_SOURCE_FILES) and max_tickers is None:
            # Default to the preferred daily VN30 set rather than every raw cache shard.
            if len(tickers_seen) >= 36:
                break
    return normalize_ohlcv_rows(selected)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _direction(value: float) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _feature_row(rows: list[dict], index: int, returns: list[float | None]) -> dict[str, float]:
    current = rows[index]
    close_value = current["close"]
    open_value = current["open"]
    prev_close = rows[index - 1]["close"] if index > 0 else close_value
    features: dict[str, float] = {}
    for lag in (1, 2, 3, 5, 10, 20):
        source_index = index - lag + 1
        features[f"feature_lag_return_{lag}"] = (
            returns[source_index] if source_index >= 0 and returns[source_index] is not None else 0.0
        )
    for window in (5, 10, 20, 40):
        return_window = [value for value in returns[max(1, index - window + 1) : index + 1] if value is not None]
        volume_window = [row["volume"] for row in rows[max(0, index - window + 1) : index + 1]]
        mean_return = _mean(return_window) or 0.0
        volatility = _std(return_window) or 0.0
        volume_mean = _mean(volume_window) or 0.0
        volume_std = _std(volume_window) or 0.0
        features[f"feature_rolling_mean_return_{window}"] = mean_return
        features[f"feature_rolling_volatility_{window}"] = volatility
        features[f"feature_rolling_volume_mean_{window}"] = volume_mean
        if window == 20:
            features["feature_rolling_volume_zscore"] = (
                0.0 if volume_std == 0 else (current["volume"] - volume_mean) / volume_std
            )
    features["feature_high_low_range"] = 0.0 if close_value == 0 else (current["high"] - current["low"]) / close_value
    features["feature_high_low_range_pct"] = features["feature_high_low_range"]
    features["feature_intrabar_range"] = features["feature_high_low_range"]
    features["feature_close_open_return"] = 0.0 if open_value == 0 else (close_value - open_value) / open_value
    features["feature_close_to_prev_close"] = 0.0 if prev_close == 0 else (close_value - prev_close) / prev_close
    for window in (5, 10, 20):
        if index >= window and rows[index - window]["close"] != 0:
            momentum = (close_value - rows[index - window]["close"]) / rows[index - window]["close"]
        else:
            momentum = 0.0
        features[f"feature_momentum_{window}"] = momentum
        features[f"feature_reversal_{window}"] = -momentum
        rolling_closes = [row["close"] for row in rows[max(0, index - window + 1) : index + 1]]
        rolling_max = max(rolling_closes) if rolling_closes else close_value
        rolling_mean = _mean(rolling_closes) or close_value
        features[f"feature_drawdown_from_rolling_max_{window}"] = 0.0 if rolling_max == 0 else (close_value - rolling_max) / rolling_max
        features[f"feature_distance_to_rolling_mean_{window}"] = 0.0 if rolling_mean == 0 else (close_value - rolling_mean) / rolling_mean
    vol_20 = features.get("feature_rolling_volatility_20", 0.0)
    vol_40 = features.get("feature_rolling_volatility_40", 0.0)
    vol_ratio = 0.0 if vol_40 == 0 else vol_20 / vol_40
    features["feature_volatility_regime_bucket"] = 2.0 if vol_ratio > 1.25 else 1.0 if vol_ratio > 0.75 else 0.0
    volume_z = features.get("feature_rolling_volume_zscore", 0.0)
    features["feature_volume_regime_bucket"] = 2.0 if volume_z > 1.0 else 0.0 if volume_z < -1.0 else 1.0
    features["feature_missing_rolling_20_flag"] = 1.0 if index < 20 else 0.0
    features["feature_missing_rolling_40_flag"] = 1.0 if index < 40 else 0.0
    return features


def build_supervised_direction_dataset(
    bars: list[dict],
    *,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict:
    """Build ticker-aware supervised rows with future targets and past/current features only."""

    normalized = normalize_ohlcv_rows(bars)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in normalized:
        grouped[row["ticker"]].append(row)

    dataset_rows: list[dict[str, Any]] = []
    skipped_without_future = 0
    rows_by_ticker_horizon: Counter[str] = Counter()
    base_future_returns: dict[tuple[str, str, int], float] = {}

    per_ticker_returns: dict[str, list[float | None]] = {}
    for ticker, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: row["timestamp"])
        grouped[ticker] = ordered
        returns = [None]
        for index in range(1, len(ordered)):
            previous = ordered[index - 1]["close"]
            returns.append(0.0 if previous == 0 else (ordered[index]["close"] - previous) / previous)
        per_ticker_returns[ticker] = returns

    for ticker, rows in grouped.items():
        if len(rows) < MIN_ROWS_PER_TICKER:
            continue
        returns = per_ticker_returns[ticker]
        for index, row in enumerate(rows):
            for horizon in horizons:
                future_index = index + int(horizon)
                if future_index >= len(rows):
                    skipped_without_future += 1
                    continue
                future_close = rows[future_index]["close"]
                current_close = row["close"]
                future_return = 0.0 if current_close == 0 else (future_close - current_close) / current_close
                features = _feature_row(rows, index, returns)
                output = {
                    "ticker": ticker,
                    "timestamp": row["timestamp"],
                    "horizon": int(horizon),
                    "future_timestamp": rows[future_index]["timestamp"],
                    "future_return": future_return,
                    "future_direction": _direction(future_return),
                    "close": row["close"],
                    **features,
                }
                base_future_returns[(ticker, row["timestamp"], int(horizon))] = future_return
                dataset_rows.append(output)
                rows_by_ticker_horizon[f"{ticker}|h{horizon}"] += 1

    for row in dataset_rows:
        market_return = base_future_returns.get(("VN30", row["timestamp"], row["horizon"]))
        if market_return is not None and row["ticker"] != "VN30":
            relative_return = float(row["future_return"]) - market_return
            row["market_future_return"] = market_return
            row["market_relative_return"] = relative_return
            row["market_relative_direction"] = _direction(relative_return)
        volatility = row.get("feature_rolling_volatility_10") or 0.0
        row["volatility_adjusted_future_return"] = (
            float(row["future_return"]) / volatility if volatility > 0 else float(row["future_return"])
        )

    by_timestamp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dataset_rows:
        by_timestamp[str(row["timestamp"])].append(row)
    for timestamp_rows in by_timestamp.values():
        lag_values = [float(row.get("feature_lag_return_1") or 0.0) for row in timestamp_rows]
        mean_lag = _mean(lag_values) or 0.0
        std_lag = _std(lag_values) or 0.0
        market_vol = _mean([float(row.get("feature_rolling_volatility_20") or 0.0) for row in timestamp_rows]) or 0.0
        sorted_values = sorted(lag_values)
        denominator = max(len(sorted_values) - 1, 1)
        for row in timestamp_rows:
            lag_value = float(row.get("feature_lag_return_1") or 0.0)
            rank_index = sorted_values.index(lag_value) if sorted_values else 0
            row["feature_ticker_relative_return_zscore"] = 0.0 if std_lag == 0 else (lag_value - mean_lag) / std_lag
            row["feature_cross_sectional_return_rank"] = rank_index / denominator
            row["feature_market_equal_weight_return"] = mean_lag if len(timestamp_rows) >= 2 else 0.0
            row["feature_market_wide_volatility"] = market_vol if len(timestamp_rows) >= 2 else 0.0
            row["feature_cross_sectional_count"] = float(len(timestamp_rows))

    feature_columns = sorted(key for key in dataset_rows[0] if key.startswith("feature_")) if dataset_rows else []
    return {
        "dataset_status": "ready" if dataset_rows else "not_ready_no_supervised_rows",
        "input_bar_count": len(normalized),
        "dataset_row_count": len(dataset_rows),
        "ticker_count": len({row["ticker"] for row in dataset_rows}),
        "horizons": list(horizons),
        "feature_columns": feature_columns,
        "rows_by_ticker_horizon": dict(sorted(rows_by_ticker_horizon.items())),
        "skipped_rows_without_future_bars": skipped_without_future,
        "rows": dataset_rows,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    allowed = (".tmp_full_model_run", ".tmp_performance_rescue")
    if not any(part.lower().startswith(allowed) for part in path.parts):
        raise ValueError("write-output must be under .tmp_full_model_run or .tmp_performance_rescue")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def render_training_dataset_report(result: dict) -> str:
    """Render a compact dataset report."""

    lines = [
        "# Local Training Dataset Builder",
        "",
        f"Dataset status: {result.get('dataset_status')}",
        f"Input bars: {result.get('input_bar_count')}",
        f"Dataset rows: {result.get('dataset_row_count')}",
        f"Ticker count: {result.get('ticker_count')}",
        f"Horizons: {result.get('horizons')}",
        f"Feature columns: {len(result.get('feature_columns') or [])}",
        f"Skipped rows without future bars: {result.get('skipped_rows_without_future_bars')}",
        "",
        "Boundary:",
        "Features use past/current bars only; targets use future local bars for supervised evaluation.",
        "No provider call, model training, model update, or file write happens unless explicitly requested.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local supervised rows from discovered OHLCV bars.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--write-output", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    bars = list(load_discovered_ohlcv_rows(repo_root=args.repo_root, max_tickers=args.max_tickers))
    result = build_supervised_direction_dataset(bars)
    if args.write_output:
        _write_jsonl(Path(args.write_output), result["rows"])
        result = {**result, "written_output": args.write_output}
    public_result = {key: value for key, value in result.items() if key != "rows"}
    if args.format == "report":
        print(render_training_dataset_report(public_result), end="")
    else:
        print(json.dumps(public_result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
