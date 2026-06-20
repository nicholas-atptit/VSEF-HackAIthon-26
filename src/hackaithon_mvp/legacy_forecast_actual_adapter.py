"""Convert legacy local prediction artifacts into MVP forecast-actual rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


PREDICTION_DIRECTION_ALIASES = ("y_pred", "pred", "prediction", "predicted_direction", "direction_pred")
ACTUAL_DIRECTION_ALIASES = ("y_true", "actual", "label", "actual_direction", "direction_true")
TIMESTAMP_ALIASES = ("prediction_timestamp", "timestamp", "datetime", "date", "time")
ACTUAL_RETURN_ALIASES = ("actual_future_return", "actual_return")
PREDICTED_RETURN_ALIASES = ("predicted_return", "prediction_return")
HORIZON_ALIASES = ("horizon_steps", "horizon")
TIMEFRAME_ALIASES = ("timeframe",)
FREQUENCY_ALIASES = ("frequency",)
MODEL_KEY_ALIASES = ("model_key", "model_id", "model")
MODEL_FAMILY_ALIASES = ("model_family", "model_group", "method_group", "candidate_family", "model")
ENGINE_ID_ALIASES = ("engine_id", "candidate_id", "source_run_id")
SCORE_ALIASES = ("diagnostic_score", "y_score_or_probability")
CONFIDENCE_ALIASES = ("confidence",)
SPLIT_ALIASES = ("split_id", "split")
ACTUAL_TIMESTAMP_ALIASES = ("actual_timestamp", "future_datetime")

WARNING_DIRECTION_ONLY = "actual_return_magnitude_unavailable_direction_only"
WARNING_SYNTHETIC_TIMESTAMP = "synthetic_row_index_timestamp_used"


def _non_empty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _clean_key_map(row: dict[str, Any]) -> dict[str, str]:
    return {str(key).strip().lower(): str(key) for key in row}


def _first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any | None:
    key_map = _clean_key_map(row)
    for alias in aliases:
        key = key_map.get(alias.lower())
        if key is not None and _non_empty(row.get(key)):
            return row[key]
    return None


def _required_value(row: dict[str, Any], aliases: tuple[str, ...], field_name: str) -> Any:
    value = _first_value(row, aliases)
    if not _non_empty(value):
        raise ValueError(f"missing required legacy field or default: {field_name}")
    return value


def _safe_float(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(str(value).strip())
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


def _direction_label_from_value(value: Any, field_name: str) -> str:
    text = str(value).strip().lower()
    if text in {"1", "1.0", "true", "positive", "up"}:
        return "positive"
    if text in {"0", "0.0", "false", "negative", "down"}:
        return "negative"
    if text in {"flat", "neutral", "0.5"}:
        return "flat"
    raise ValueError(f"unsupported {field_name}: {value!r}")


def _direction_label_from_return(value: Any) -> str:
    number = _safe_float(value, "actual_return")
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "flat"


def _forecast_diagnostic_from_direction(value: Any) -> str:
    label = _direction_label_from_value(value, "prediction direction")
    if label == "positive":
        return "positive_bias"
    if label == "negative":
        return "negative_bias"
    return "neutral_or_uncertain"


def _forecast_diagnostic_from_return(value: Any) -> str:
    number = _safe_float(value, "predicted_return")
    if number > 0:
        return "positive_bias"
    if number < 0:
        return "negative_bias"
    return "neutral_or_uncertain"


def _timeframe_from_frequency(value: Any, horizon_steps: int) -> str:
    frequency = str(value).strip().lower()
    if frequency in {"hourly", "hour", "h", "1h"}:
        return normalize_timeframe("1h")
    if frequency in {"daily", "day", "d", "1d"}:
        return normalize_timeframe("1d")
    if frequency in {"minute", "min", "m"}:
        return normalize_timeframe("1m")
    raise ValueError(f"unsupported legacy frequency: {value!r}")


def _resolve_timeframe(row: dict[str, Any], default_timeframe: str | None, horizon_steps: int) -> str:
    value = _first_value(row, TIMEFRAME_ALIASES)
    if _non_empty(value):
        return normalize_timeframe(str(value))
    if default_timeframe is not None:
        return normalize_timeframe(default_timeframe)
    frequency = _first_value(row, FREQUENCY_ALIASES)
    if _non_empty(frequency):
        return _timeframe_from_frequency(frequency, horizon_steps)
    raise ValueError("missing required legacy field or default: timeframe")


def _optional_string(row: dict[str, Any], aliases: tuple[str, ...]) -> str | None:
    value = _first_value(row, aliases)
    if not _non_empty(value):
        return None
    return str(value).strip()


def _optional_float(row: dict[str, Any], aliases: tuple[str, ...], field_name: str) -> float | None:
    value = _first_value(row, aliases)
    if not _non_empty(value):
        return None
    return _safe_float(value, field_name)


def load_legacy_rows(path: str) -> tuple[dict, ...]:
    """Load legacy rows from CSV, JSON, or JSONL."""

    local_path = Path(path)
    if not local_path.exists() or not local_path.is_file():
        raise FileNotFoundError(f"legacy input file not found: {path}")
    suffix = local_path.suffix.lower()
    if suffix == ".csv":
        with local_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    elif suffix == ".json":
        payload = json.loads(local_path.read_text(encoding="utf-8-sig"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
    elif suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in local_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    else:
        raise ValueError("legacy input must be .csv, .json, or .jsonl")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("legacy payload must contain row objects")
    return tuple(rows)


def convert_legacy_rows_to_forecast_actual(
    rows: tuple[dict, ...],
    *,
    default_ticker: str | None = None,
    default_timeframe: str | None = None,
    default_horizon_steps: int | None = None,
    allow_row_index_timestamp: bool = False,
    source_name: str | None = None,
) -> tuple[dict, ...]:
    """Convert legacy row-level artifacts into forecast-actual evaluator rows."""

    converted: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        ticker = _first_value(row, ("ticker",))
        if not _non_empty(ticker):
            ticker = default_ticker
        if not _non_empty(ticker):
            raise ValueError("missing required legacy field or default: ticker")

        horizon_value = _first_value(row, HORIZON_ALIASES)
        if not _non_empty(horizon_value):
            horizon_value = default_horizon_steps
        if not _non_empty(horizon_value):
            raise ValueError("missing required legacy field or default: horizon_steps")
        horizon_steps = _safe_int(horizon_value, "horizon_steps")
        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")

        timestamp = _first_value(row, TIMESTAMP_ALIASES)
        synthetic_timestamp = False
        if not _non_empty(timestamp):
            if not allow_row_index_timestamp:
                raise ValueError("missing required legacy field: prediction_timestamp")
            timestamp = f"row_index_{index}"
            synthetic_timestamp = True

        predicted_return = _first_value(row, PREDICTED_RETURN_ALIASES)
        if _non_empty(predicted_return):
            forecast_diagnostic = _forecast_diagnostic_from_return(predicted_return)
        else:
            prediction_value = _required_value(row, PREDICTION_DIRECTION_ALIASES, "prediction direction")
            forecast_diagnostic = _forecast_diagnostic_from_direction(prediction_value)

        actual_return = _first_value(row, ACTUAL_RETURN_ALIASES)
        direction_only = False
        if _non_empty(actual_return):
            actual_future_return = _safe_float(actual_return, "actual_return")
            actual_direction_label = _direction_label_from_return(actual_future_return)
        else:
            actual_value = _required_value(row, ACTUAL_DIRECTION_ALIASES, "actual direction")
            actual_direction_label = _direction_label_from_value(actual_value, "actual direction")
            if actual_direction_label == "positive":
                actual_future_return = 1.0
            elif actual_direction_label == "negative":
                actual_future_return = -1.0
            else:
                actual_future_return = 0.0
            direction_only = True

        output: dict[str, Any] = {
            "ticker": str(ticker).strip(),
            "timeframe": _resolve_timeframe(row, default_timeframe, horizon_steps),
            "prediction_timestamp": str(timestamp).strip(),
            "horizon_steps": horizon_steps,
            "forecast_diagnostic": forecast_diagnostic,
            "actual_future_return": actual_future_return,
            "actual_direction_label": actual_direction_label,
        }
        optional_values = {
            "engine_id": _optional_string(row, ENGINE_ID_ALIASES),
            "model_key": _optional_string(row, MODEL_KEY_ALIASES),
            "model_family": _optional_string(row, MODEL_FAMILY_ALIASES),
            "diagnostic_score": _optional_float(row, SCORE_ALIASES, "diagnostic_score"),
            "confidence": _optional_float(row, CONFIDENCE_ALIASES, "confidence"),
            "split_id": _optional_string(row, SPLIT_ALIASES),
            "actual_timestamp": _optional_string(row, ACTUAL_TIMESTAMP_ALIASES),
            "source": source_name,
        }
        for field, value in optional_values.items():
            if value not in (None, ""):
                output[field] = value
        if direction_only:
            output[WARNING_DIRECTION_ONLY] = True
        if synthetic_timestamp:
            output[WARNING_SYNTHETIC_TIMESTAMP] = True
        converted.append(output)
    return tuple(converted)


def summarize_conversion(rows: tuple[dict, ...]) -> dict:
    warnings = Counter()
    forecast_counts = Counter()
    actual_counts = Counter()
    timeframe_counts = Counter()
    model_family_counts = Counter()
    for row in rows:
        if row.get(WARNING_DIRECTION_ONLY) is True:
            warnings[WARNING_DIRECTION_ONLY] += 1
        if row.get(WARNING_SYNTHETIC_TIMESTAMP) is True:
            warnings[WARNING_SYNTHETIC_TIMESTAMP] += 1
        forecast_counts[str(row.get("forecast_diagnostic", "missing"))] += 1
        actual_counts[str(row.get("actual_direction_label", "missing"))] += 1
        timeframe_counts[str(row.get("timeframe", "missing"))] += 1
        model_family_counts[str(row.get("model_family", "unspecified"))] += 1
    return {
        "rows_total": len(rows),
        "forecast_diagnostic_counts": dict(sorted(forecast_counts.items())),
        "actual_direction_label_counts": dict(sorted(actual_counts.items())),
        "timeframe_counts": dict(sorted(timeframe_counts.items())),
        "model_family_counts": dict(sorted(model_family_counts.items())),
        "warnings": dict(sorted(warnings.items())),
        "direction_only_placeholder_return_used": warnings[WARNING_DIRECTION_ONLY] > 0,
    }


def _write_rows(path: str, rows: tuple[dict, ...], output_format: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "jsonl":
        output = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    else:
        output = json.dumps(list(rows), indent=2, sort_keys=True) + "\n"
    output_path.write_text(output, encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert local legacy row artifacts into MVP forecast-actual rows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--horizon-steps", type=int, default=None)
    parser.add_argument("--allow-row-index-timestamp", action="store_true")
    parser.add_argument("--format", choices=("json", "jsonl"), default="json")
    parser.add_argument("--write", default=None)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--top-k", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        legacy_rows = load_legacy_rows(args.input)
        converted_rows = convert_legacy_rows_to_forecast_actual(
            legacy_rows,
            default_ticker=args.ticker,
            default_timeframe=args.timeframe,
            default_horizon_steps=args.horizon_steps,
            allow_row_index_timestamp=args.allow_row_index_timestamp,
            source_name=args.input,
        )
        summary = summarize_conversion(converted_rows)
        if args.write:
            written_path = _write_rows(args.write, converted_rows, args.format)
            summary["written_path"] = str(written_path)
        if args.evaluate:
            evaluation = evaluate_forecast_vs_actual(converted_rows, top_k=args.top_k)
            output = {"conversion_summary": summary, "evaluation": evaluation}
        else:
            output = {"conversion_summary": summary}
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
