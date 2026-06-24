"""Gate a 60 percent forecast attempt on genuinely expanded local data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.data_expanded_forecast_contract import (
    REQUIRED_PRICE_COLUMNS,
    load_expanded_price_panel,
    validate_expanded_price_panel_schema,
)


STATUS_AVAILABLE = "real_expanded_data_available"
STATUS_REQUIRED = "expanded_data_required_for_60pct_attempt"
STATUS_OHLCV_ONLY = "expanded_data_missing_ohlcv_only"
STATUS_INSUFFICIENT_CONTEXT = "expanded_data_insufficient_context"
STATUS_INVALID_SCHEMA = "expanded_data_invalid_schema"
STATUS_INPUT_NOT_FOUND = "expanded_data_input_not_found"
MIN_ADDITIONAL_GROUPS = 2
CLAIM_BOUNDARY = {
    "requires_ohlcv": True,
    "requires_two_additional_context_groups": True,
    "ohlcv_only_is_not_data_expanded": True,
    "no_training": True,
    "no_forecast_claim": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = (
    "Real expanded-data requirement checks local data readiness only; "
    "it does not compute forecast accuracy."
)


def _columns(rows: list[dict]) -> set[str]:
    return {str(key).strip().lower() for row in rows if isinstance(row, dict) for key in row}


def _value(row: dict[str, Any], key: str) -> Any:
    for actual_key, value in row.items():
        if str(actual_key).strip().lower() == key:
            return value
    return None


def _has_intraday_granularity(rows: list[dict]) -> bool:
    for row in rows:
        raw = _value(row, "timestamp")
        if raw in (None, ""):
            continue
        text = str(raw).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            if " " in text or "T" in text:
                time_part = text.split("T")[-1].split(" ")[-1]
                if time_part and not time_part.startswith("00:00"):
                    return True
            continue
        if parsed.hour or parsed.minute or parsed.second or parsed.microsecond:
            return True
    return False


def _additional_groups(rows: list[dict]) -> dict[str, dict[str, Any]]:
    fields = _columns(rows)
    groups = {
        "adjusted_price": ["adjusted_close"],
        "turnover_or_value": ["turnover", "vwap"],
        "market_cap": ["market_cap"],
        "foreign_flow": ["foreign_buy", "foreign_sell", "foreign_net"],
        "sector_or_industry": ["sector", "industry"],
        "index_context": ["index_vnindex_close", "index_vn30_close", "index_return"],
        "sector_return": ["sector_return"],
        "news_context": ["news_score"],
        "event_context": ["event_flag"],
    }
    result: dict[str, dict[str, Any]] = {}
    for group, columns in groups.items():
        present = [column for column in columns if column in fields]
        result[group] = {"available": bool(present), "columns_present": present}
    intraday = _has_intraday_granularity(rows)
    result["intraday_granularity"] = {
        "available": intraday,
        "columns_present": ["timestamp"] if intraday else [],
    }
    return result


def _discover_panel(output_root: str | Path | None) -> Path | None:
    if not output_root:
        return None
    root = Path(output_root)
    if not root.exists():
        return None
    candidates = []
    for search_root in (root, root / "data"):
        if not search_root.exists():
            continue
        for path in search_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".csv", ".jsonl", ".json"}:
                continue
            name = path.name.lower()
            if "price" in name or "panel" in name or "ohlcv" in name:
                candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.stat().st_size, str(item)), reverse=True)[0]


def _base_result(*, status: str, input_path: str | None, reason: str) -> dict:
    return {
        "expanded_data_requirement_status": status,
        "real_expanded_data_available": False,
        "input_path": input_path,
        "reason": reason,
        "minimum_additional_context_groups": MIN_ADDITIONAL_GROUPS,
        "additional_context_group_count": 0,
        "additional_context_groups": {},
        "missing_required_columns": [],
        "is_ohlcv_only": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def check_real_expanded_data_available(
    *,
    input_path: str | None = None,
    output_root: str | None = None,
) -> dict:
    """Return whether a local panel is truly expanded beyond OHLCV."""

    selected = Path(input_path) if input_path else _discover_panel(output_root)
    if selected is None:
        return _base_result(
            status=STATUS_REQUIRED,
            input_path=None,
            reason="no_expanded_input_file_or_provider_panel_found",
        )
    if not selected.exists() or not selected.is_file():
        return _base_result(
            status=STATUS_INPUT_NOT_FOUND,
            input_path=str(selected),
            reason="expanded_input_file_not_found",
        )

    try:
        rows = load_expanded_price_panel(selected)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = _base_result(
            status=STATUS_INVALID_SCHEMA,
            input_path=str(selected),
            reason=f"unable_to_load_expanded_panel:{type(exc).__name__}",
        )
        return result

    contract = validate_expanded_price_panel_schema(rows)
    missing = list(contract.get("missing_required_columns") or [])
    groups = _additional_groups(rows)
    present_groups = sorted(group for group, detail in groups.items() if detail.get("available"))
    group_count = len(present_groups)
    observed_columns = set(contract.get("observed_columns") or [])
    required_columns = set(REQUIRED_PRICE_COLUMNS)
    is_ohlcv_only = bool(rows) and not missing and observed_columns.issubset(required_columns)

    if contract.get("contract_status") != "valid" or missing:
        status = STATUS_INVALID_SCHEMA
        reason = "required_ohlcv_schema_invalid"
    elif is_ohlcv_only or group_count == 0:
        status = STATUS_OHLCV_ONLY
        reason = "panel_contains_only_ticker_timestamp_ohlcv"
    elif group_count < MIN_ADDITIONAL_GROUPS:
        status = STATUS_INSUFFICIENT_CONTEXT
        reason = "fewer_than_two_additional_context_groups"
    else:
        status = STATUS_AVAILABLE
        reason = "ohlcv_plus_required_expanded_context_available"

    return {
        "expanded_data_requirement_status": status,
        "real_expanded_data_available": status == STATUS_AVAILABLE,
        "input_path": str(selected),
        "reason": reason,
        "rows": len(rows),
        "contract_status": contract.get("contract_status"),
        "missing_required_columns": missing,
        "observed_columns": sorted(observed_columns),
        "required_columns": list(REQUIRED_PRICE_COLUMNS),
        "additional_context_groups": groups,
        "additional_context_groups_present": present_groups,
        "additional_context_group_count": group_count,
        "minimum_additional_context_groups": MIN_ADDITIONAL_GROUPS,
        "is_ohlcv_only": is_ohlcv_only,
        "ticker_coverage": contract.get("ticker_coverage"),
        "timestamp_coverage": contract.get("timestamp_coverage"),
        "duplicate_timestamp_audit": contract.get("duplicate_timestamp_audit"),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_real_expanded_data_requirement_report(result: dict) -> str:
    """Render the real-expanded-data requirement result."""

    lines = [
        "# Real Expanded Data Requirement",
        "",
        f"Requirement status: {result.get('expanded_data_requirement_status')}",
        f"Real expanded data available: {result.get('real_expanded_data_available')}",
        f"Input path: {result.get('input_path') or 'not_provided'}",
        f"Rows: {result.get('rows', 0)}",
        f"Reason: {result.get('reason')}",
        f"Missing required columns: {result.get('missing_required_columns') or []}",
        f"Additional context groups present: {result.get('additional_context_groups_present') or []}",
        f"Additional context group count: {result.get('additional_context_group_count')}",
        f"Minimum additional context groups: {result.get('minimum_additional_context_groups')}",
        f"OHLCV only: {result.get('is_ohlcv_only')}",
        "",
        "Boundary:",
        "OHLCV-only data is not accepted as a real data-expanded 60% attempt.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether real expanded forecast data is available.")
    parser.add_argument("--input", default=None, help="Optional expanded price-panel CSV/JSONL/JSON path.")
    parser.add_argument("--output-root", default=None, help="Optional root to discover expanded panel artifacts.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = check_real_expanded_data_available(input_path=args.input, output_root=args.output_root)
    if args.format == "report":
        print(render_real_expanded_data_requirement_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
