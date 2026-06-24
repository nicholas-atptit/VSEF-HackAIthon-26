"""Schema contract for expanded local forecast price panels."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_PRICE_COLUMNS = ("ticker", "timestamp", "open", "high", "low", "close", "volume")
OPTIONAL_PRICE_COLUMNS = (
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
)
MARKET_CONTEXT_COLUMNS = ("index_vnindex_close", "index_vn30_close", "index_return")
SECTOR_CONTEXT_COLUMNS = ("sector", "industry", "sector_return")
CLAIM_BOUNDARY = {
    "local_file_only": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_forecast_claim": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Expanded-data contract validates local panel readiness only; it does not compute forecast accuracy."


def _lower_key_map(row: dict[str, Any]) -> dict[str, str]:
    return {str(key).strip().lower(): str(key) for key in row}


def _value(row: dict[str, Any], key: str) -> Any:
    actual = _lower_key_map(row).get(key.lower())
    return row.get(actual) if actual is not None else None


def _safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _present_ratio(rows: list[dict], column: str) -> float:
    if not rows:
        return 0.0
    count = sum(1 for row in rows if _value(row, column) not in (None, ""))
    return round(count / len(rows), 6)


def _columns(rows: list[dict]) -> set[str]:
    return {str(key).strip().lower() for row in rows if isinstance(row, dict) for key in row}


def _timestamp_range(values: list[str]) -> dict[str, Any]:
    clean = sorted(value for value in values if value)
    return {
        "first_timestamp": clean[0] if clean else None,
        "last_timestamp": clean[-1] if clean else None,
        "unique_timestamp_count": len(set(clean)),
    }


def validate_expanded_price_panel_schema(rows: list[dict]) -> dict:
    """Validate expanded local price-panel schema and coverage."""

    clean_rows = [row for row in rows if isinstance(row, dict)]
    fields = _columns(clean_rows)
    missing = [column for column in REQUIRED_PRICE_COLUMNS if column not in fields]
    optional_present = [column for column in OPTIONAL_PRICE_COLUMNS if column in fields]
    ticker_values = [str(_value(row, "ticker")).strip().upper() for row in clean_rows if _value(row, "ticker") not in (None, "")]
    timestamp_values = [str(_value(row, "timestamp")).strip() for row in clean_rows if _value(row, "timestamp") not in (None, "")]
    duplicate_counter: Counter[tuple[str, str]] = Counter()
    rows_by_ticker: Counter[str] = Counter()
    invalid_price_rows = 0
    invalid_volume_rows = 0
    for row in clean_rows:
        ticker = str(_value(row, "ticker") or "").strip().upper()
        timestamp = str(_value(row, "timestamp") or "").strip()
        if ticker and timestamp:
            duplicate_counter[(ticker, timestamp)] += 1
            rows_by_ticker[ticker] += 1
        open_value = _safe_float(_value(row, "open"))
        high_value = _safe_float(_value(row, "high"))
        low_value = _safe_float(_value(row, "low"))
        close_value = _safe_float(_value(row, "close"))
        volume_value = _safe_float(_value(row, "volume"))
        if None in (open_value, high_value, low_value, close_value) or (
            high_value is not None and low_value is not None and high_value < low_value
        ):
            invalid_price_rows += 1
        if volume_value is None or volume_value < 0:
            invalid_volume_rows += 1
    duplicates = {f"{ticker}|{timestamp}": count for (ticker, timestamp), count in duplicate_counter.items() if count > 1}
    adjusted_ratio = _present_ratio(clean_rows, "adjusted_close")
    market_columns_present = [column for column in MARKET_CONTEXT_COLUMNS if column in fields]
    sector_columns_present = [column for column in SECTOR_CONTEXT_COLUMNS if column in fields]
    status = "valid" if clean_rows and not missing and not invalid_price_rows and not invalid_volume_rows else "invalid"
    return {
        "contract_status": status,
        "input_rows": len(rows),
        "valid_row_objects": len(clean_rows),
        "required_columns": list(REQUIRED_PRICE_COLUMNS),
        "optional_columns": list(OPTIONAL_PRICE_COLUMNS),
        "observed_columns": sorted(fields),
        "missing_required_columns": missing,
        "optional_columns_present": optional_present,
        "ticker_coverage": {
            "ticker_count": len(set(ticker_values)),
            "tickers": sorted(set(ticker_values)),
            "rows_by_ticker": dict(sorted(rows_by_ticker.items())),
        },
        "timestamp_coverage": _timestamp_range(timestamp_values),
        "duplicate_timestamp_audit": {
            "duplicate_key_count": sum(count - 1 for count in duplicate_counter.values() if count > 1),
            "duplicate_keys": duplicates,
            "duplicate_severity": "high" if duplicates else "none",
        },
        "adjusted_price_availability": {
            "available": adjusted_ratio > 0.0,
            "coverage_ratio": adjusted_ratio,
        },
        "market_context_availability": {
            "available": bool(market_columns_present),
            "columns_present": market_columns_present,
        },
        "sector_context_availability": {
            "available": bool(sector_columns_present),
            "columns_present": sector_columns_present,
        },
        "quality_issues": {
            "invalid_price_rows": invalid_price_rows,
            "invalid_volume_rows": invalid_volume_rows,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def load_expanded_price_panel(path: str | Path) -> list[dict[str, Any]]:
    """Load a local expanded price panel from CSV, JSONL, or JSON."""

    local_path = Path(path)
    if not local_path.exists() or not local_path.is_file():
        raise FileNotFoundError(f"expanded price panel not found: {path}")
    suffix = local_path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(local_path)
    if suffix == ".jsonl":
        return _load_jsonl(local_path)
    if suffix == ".json":
        payload = json.loads(local_path.read_text(encoding="utf-8-sig"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
            return rows
        raise ValueError("JSON panel must be a list of objects or an object with rows")
    raise ValueError("expanded price panel must be .csv, .jsonl, or .json")


def validate_expanded_price_panel_file(path: str | Path) -> dict:
    """Load and validate a local expanded price panel file."""

    rows = load_expanded_price_panel(path)
    result = validate_expanded_price_panel_schema(rows)
    result["input_path"] = str(path)
    return result


def render_data_expanded_forecast_contract_report(result: dict) -> str:
    """Render expanded-data contract validation report."""

    ticker = result.get("ticker_coverage") or {}
    timestamp = result.get("timestamp_coverage") or {}
    duplicate = result.get("duplicate_timestamp_audit") or {}
    adjusted = result.get("adjusted_price_availability") or {}
    market = result.get("market_context_availability") or {}
    sector = result.get("sector_context_availability") or {}
    quality = result.get("quality_issues") or {}
    lines = [
        "# Data-Expanded Forecast Contract",
        "",
        f"Contract status: {result.get('contract_status')}",
        f"Input path: {result.get('input_path', 'not_provided')}",
        f"Rows: {result.get('valid_row_objects')}",
        f"Missing required columns: {result.get('missing_required_columns') or []}",
        f"Optional columns present: {result.get('optional_columns_present') or []}",
        f"Ticker count: {ticker.get('ticker_count')}",
        f"Timestamp range: {timestamp.get('first_timestamp')} -> {timestamp.get('last_timestamp')}",
        f"Unique timestamps: {timestamp.get('unique_timestamp_count')}",
        f"Duplicate ticker/timestamp rows: {duplicate.get('duplicate_key_count')}",
        f"Duplicate severity: {duplicate.get('duplicate_severity')}",
        f"Adjusted close coverage: {adjusted.get('coverage_ratio')}",
        f"Market/index context available: {market.get('available')} {market.get('columns_present')}",
        f"Sector context available: {sector.get('available')} {sector.get('columns_present')}",
        f"Invalid price rows: {quality.get('invalid_price_rows')}",
        f"Invalid volume rows: {quality.get('invalid_volume_rows')}",
        "",
        "Boundary:",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a local expanded forecast price panel.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = validate_expanded_price_panel_file(args.input)
    if args.format == "report":
        print(render_data_expanded_forecast_contract_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
