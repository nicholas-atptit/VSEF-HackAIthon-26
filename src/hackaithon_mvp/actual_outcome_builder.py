"""Build forecast-vs-actual rows from local forecast rows and realized bar rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.data_contracts import BarRecord
from src.hackaithon_mvp.forecast_actual_evaluation import (
    ALLOWED_FORECAST_DIAGNOSTICS,
    evaluate_forecast_vs_actual,
)
from src.hackaithon_mvp.local_storage.parquet_adapter import read_dataset_records
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


REQUIRED_FORECAST_FIELDS = (
    "ticker",
    "timeframe",
    "prediction_timestamp",
    "horizon_steps",
    "forecast_diagnostic",
)
OPTIONAL_FORECAST_FIELDS = (
    "engine_id",
    "model_key",
    "model_family",
    "diagnostic_score",
    "confidence",
    "route",
    "risk_level",
    "split_id",
    "source",
    "policy_id",
    "policy_name",
    "policy_runtime_status",
)
REQUIRED_BAR_FIELDS = ("ticker", "timeframe", "timestamp", "open", "high", "low", "close", "volume")
TIMESTAMP_ALIASES = ("timestamp", "time", "datetime")
TIMEFRAME_ALIASES = ("timeframe", "frequency")
ALLOWED_MATCH_MODES = frozenset({"exact", "nearest_prior"})
CLAIM_BOUNDARY = {
    "local_rows_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "missing_actuals_are_skipped": True,
}
NON_CLAIM_TEXT = "Actual outcomes are derived only from provided local bar rows."


def _load_json_payload(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON payload must be a list of objects or an object with rows")
    return rows


def load_local_rows(path: str) -> tuple[dict, ...]:
    """Load local CSV, JSON, or JSONL rows."""

    local_path = Path(path)
    if not local_path.exists() or not local_path.is_file():
        raise FileNotFoundError(f"local input file not found: {path}")
    suffix = local_path.suffix.lower()
    if suffix == ".csv":
        with local_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    elif suffix == ".json":
        rows = _load_json_payload(local_path)
    elif suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in local_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("JSONL payload must contain objects")
    else:
        raise ValueError("local input must be .csv, .json, or .jsonl")
    return tuple(dict(row) for row in rows)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be datetime-like") from exc


def _timestamp_text(value: Any, field_name: str) -> str:
    text = str(value).strip()
    _parse_datetime(text, field_name)
    return text


def _safe_float(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number:
        raise ValueError(f"{field_name} must be numeric")
    return number


def _safe_int(value: Any, field_name: str) -> int:
    number = _safe_float(value, field_name)
    if int(number) != number:
        raise ValueError(f"{field_name} must be an integer")
    return int(number)


def _first_present(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    key_map = {str(key).strip().lower(): key for key in row}
    for alias in aliases:
        key = key_map.get(alias)
        if key is not None and row.get(key) not in (None, ""):
            return row[key]
    return None


def _normalize_forecast_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FORECAST_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing required forecast fields: {missing}")
    ticker = str(row["ticker"]).strip().upper()
    if not ticker:
        raise ValueError("ticker must be non-empty")
    timeframe = normalize_timeframe(str(row["timeframe"]))
    horizon_steps = _safe_int(row["horizon_steps"], "horizon_steps")
    if horizon_steps <= 0:
        raise ValueError("horizon_steps must be positive")
    forecast_diagnostic = str(row["forecast_diagnostic"]).strip()
    if forecast_diagnostic not in ALLOWED_FORECAST_DIAGNOSTICS:
        raise ValueError(f"unsupported forecast_diagnostic: {forecast_diagnostic}")

    normalized: dict[str, Any] = {
        "ticker": ticker,
        "timeframe": timeframe,
        "prediction_timestamp": _timestamp_text(row["prediction_timestamp"], "prediction_timestamp"),
        "prediction_datetime": _parse_datetime(row["prediction_timestamp"], "prediction_timestamp"),
        "horizon_steps": horizon_steps,
        "forecast_diagnostic": forecast_diagnostic,
    }
    for field in OPTIONAL_FORECAST_FIELDS:
        value = row.get(field)
        if value in (None, ""):
            continue
        if field in {"diagnostic_score", "confidence"}:
            normalized[field] = _safe_float(value, field)
        else:
            normalized[field] = str(value).strip()
    return normalized


def _normalize_bar_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized_input = dict(row)
    timestamp = _first_present(normalized_input, TIMESTAMP_ALIASES)
    timeframe = _first_present(normalized_input, TIMEFRAME_ALIASES)
    if timestamp is not None:
        normalized_input["timestamp"] = timestamp
    if timeframe is not None:
        normalized_input["timeframe"] = timeframe
    missing = [field for field in REQUIRED_BAR_FIELDS if field not in normalized_input]
    if missing:
        raise ValueError(f"missing required bar fields: {missing}")

    bar = BarRecord(
        ticker=str(normalized_input["ticker"]).strip().upper(),
        timeframe=str(normalized_input["timeframe"]),
        timestamp=_timestamp_text(normalized_input["timestamp"], "timestamp"),
        open=normalized_input["open"],
        high=normalized_input["high"],
        low=normalized_input["low"],
        close=normalized_input["close"],
        volume=normalized_input["volume"],
        adjusted_close=normalized_input.get("adjusted_close"),
        source=normalized_input.get("source"),
        metadata=normalized_input.get("metadata") if isinstance(normalized_input.get("metadata"), dict) else {},
    )
    return {
        "ticker": bar.ticker,
        "timeframe": bar.timeframe,
        "timestamp": bar.timestamp,
        "timestamp_datetime": _parse_datetime(bar.timestamp, "timestamp"),
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "adjusted_close": bar.adjusted_close,
        "source": bar.source,
        "metadata": bar.metadata,
    }


def derive_actual_label(actual_future_return: float) -> str:
    """Derive the realized direction label from a local return value."""

    value = _safe_float(actual_future_return, "actual_future_return")
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "flat"


def _bar_groups(bar_rows: tuple[dict, ...]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in bar_rows:
        bar = _normalize_bar_row(row)
        groups.setdefault((bar["ticker"], bar["timeframe"]), []).append(bar)
    for rows in groups.values():
        rows.sort(key=lambda value: value["timestamp_datetime"])
    return groups


def _current_index(bars: list[dict[str, Any]], prediction_time: datetime, match_mode: str) -> int | None:
    if match_mode == "exact":
        for index, bar in enumerate(bars):
            if bar["timestamp_datetime"] == prediction_time:
                return index
        return None
    prior_indexes = [index for index, bar in enumerate(bars) if bar["timestamp_datetime"] <= prediction_time]
    return prior_indexes[-1] if prior_indexes else None


def _output_row(forecast: dict[str, Any], current_bar: dict[str, Any], future_bar: dict[str, Any]) -> dict[str, Any]:
    actual_future_return = float(future_bar["close"]) / float(current_bar["close"]) - 1.0
    output = {
        "ticker": forecast["ticker"],
        "timeframe": forecast["timeframe"],
        "prediction_timestamp": forecast["prediction_timestamp"],
        "horizon_steps": forecast["horizon_steps"],
        "forecast_diagnostic": forecast["forecast_diagnostic"],
        "actual_future_return": actual_future_return,
        "actual_direction_label": derive_actual_label(actual_future_return),
        "actual_timestamp": future_bar["timestamp"],
    }
    for field in OPTIONAL_FORECAST_FIELDS:
        if field in forecast:
            output[field] = forecast[field]
    return output


def build_actual_outcomes(
    forecast_rows: tuple[dict, ...],
    bar_rows: tuple[dict, ...],
    *,
    match_mode: str = "exact",
) -> tuple[dict, ...]:
    """Build evaluator-compatible actual outcome rows from local forecasts and bars."""

    if match_mode not in ALLOWED_MATCH_MODES:
        raise ValueError(f"unsupported match_mode: {match_mode}")
    normalized_forecasts = tuple(_normalize_forecast_row(row) for row in forecast_rows)
    grouped_bars = _bar_groups(bar_rows)
    output_rows: list[dict[str, Any]] = []
    for forecast in normalized_forecasts:
        bars = grouped_bars.get((forecast["ticker"], forecast["timeframe"]), [])
        if not bars:
            continue
        current_index = _current_index(bars, forecast["prediction_datetime"], match_mode)
        if current_index is None:
            continue
        future_index = current_index + forecast["horizon_steps"]
        if future_index >= len(bars):
            continue
        output_rows.append(_output_row(forecast, bars[current_index], bars[future_index]))
    return tuple(output_rows)


def render_actual_outcome_summary(rows: tuple[dict, ...]) -> dict:
    forecast_counts = Counter(str(row.get("forecast_diagnostic", "missing")) for row in rows)
    actual_counts = Counter(str(row.get("actual_direction_label", "missing")) for row in rows)
    timeframe_counts = Counter(str(row.get("timeframe", "missing")) for row in rows)
    ticker_counts = Counter(str(row.get("ticker", "missing")) for row in rows)
    return {
        "rows_total": len(rows),
        "actual_data_status": "provided" if rows else "missing",
        "forecast_diagnostic_counts": dict(sorted(forecast_counts.items())),
        "actual_direction_label_counts": dict(sorted(actual_counts.items())),
        "timeframe_counts": dict(sorted(timeframe_counts.items())),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_actual_outcomes_from_storage(
    forecast_rows: tuple[dict, ...],
    *,
    storage_root: str,
    ticker: str,
    timeframe: str,
    date: str | None = None,
    match_mode: str = "exact",
) -> tuple[dict, ...]:
    """Build actual outcomes using locally stored market bars."""

    bar_rows = read_dataset_records(
        storage_root,
        "market_bars",
        ticker=str(ticker).strip().upper(),
        timeframe=normalize_timeframe(timeframe),
        date=date,
    )
    if not bar_rows:
        return ()
    return build_actual_outcomes(forecast_rows, bar_rows, match_mode=match_mode)


def _write_rows(path: str, rows: tuple[dict, ...], output_format: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "jsonl":
        output = "\n".join(json.dumps(row, sort_keys=True, default=str) for row in rows)
        if output:
            output += "\n"
    else:
        output = json.dumps(list(rows), indent=2, sort_keys=True, default=str) + "\n"
    output_path.write_text(output, encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build actual outcome rows from local forecast and bar rows.")
    parser.add_argument("--forecasts", required=True)
    parser.add_argument("--bars", default=None)
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--match-mode", choices=("exact", "nearest_prior"), default="exact")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    parser.add_argument("--write", default=None)
    parser.add_argument("--evaluate", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.bars and not args.storage_root:
        parser.error("either --bars or --storage-root must be provided")
    if args.storage_root and (not args.ticker or not args.timeframe):
        parser.error("--ticker and --timeframe are required with --storage-root")
    try:
        forecast_rows = load_local_rows(args.forecasts)
        if args.storage_root:
            rows = build_actual_outcomes_from_storage(
                forecast_rows,
                storage_root=args.storage_root,
                ticker=args.ticker,
                timeframe=args.timeframe,
                date=args.date,
                match_mode=args.match_mode,
            )
        else:
            rows = build_actual_outcomes(
                forecast_rows,
                load_local_rows(args.bars),
                match_mode=args.match_mode,
            )
        summary = render_actual_outcome_summary(rows)
        if args.write:
            written_path = _write_rows(args.write, rows, args.format)
            summary["written_path"] = str(written_path)
        output = {"actual_outcome_summary": summary}
        if args.evaluate:
            output["evaluation"] = evaluate_forecast_vs_actual(rows)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
