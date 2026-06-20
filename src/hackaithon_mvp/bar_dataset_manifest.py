"""Future bar dataset manifest builder for the HackAIthon MVP storage design."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.hackaithon_mvp.data_contracts import DEFAULT_TICKERS
from src.hackaithon_mvp.storage_design import get_storage_design
from src.hackaithon_mvp.timeframe_schema import REQUIRED_TIMEFRAME_INPUTS, normalize_timeframe


MANIFEST_VERSION = "1.0"
NON_CLAIM_TEXT = "Dataset manifest only; no files, database, data gateway, or live data access are created."


def _normalize_tickers(tickers: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for ticker in tickers:
        value = str(ticker).strip().upper()
        if not value:
            raise ValueError("ticker must be non-empty")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("ticker contains unsupported path characters")
        normalized.append(value)
    return tuple(normalized)


def _normalize_timeframes(timeframe_inputs: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(normalize_timeframe(value) for value in timeframe_inputs))


def _validate_date(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty when provided")
    if "/" in text or "\\" in text or ".." in text:
        raise ValueError(f"{field_name} contains unsupported path characters")
    return text


def build_bar_dataset_manifest(
    dataset_root: str,
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    timeframe_inputs: tuple[str, ...] = REQUIRED_TIMEFRAME_INPUTS,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    root = str(dataset_root).strip().replace("\\", "/").rstrip("/")
    if not root:
        raise ValueError("dataset_root must be non-empty")
    if ".." in root:
        raise ValueError("dataset_root contains unsupported path characters")

    normalized_tickers = _normalize_tickers(tickers)
    if normalized_tickers == DEFAULT_TICKERS and len(normalized_tickers) != 30:
        raise ValueError("default ticker universe must contain 30 tickers")
    timeframes = _normalize_timeframes(timeframe_inputs)
    design = get_storage_design()
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_root": root,
        "storage_design": design,
        "tickers_count": len(normalized_tickers),
        "timeframes_count": len(timeframes),
        "tickers": list(normalized_tickers),
        "timeframes": list(timeframes),
        "partition_columns": design["partition_columns"],
        "required_bar_columns": design["required_bar_columns"],
        "optional_bar_columns": design["optional_bar_columns"],
        "start_date": _validate_date(start_date, "start_date"),
        "end_date": _validate_date(end_date, "end_date"),
        "database_created": False,
        "data_gateway_created": False,
        "live_data_enabled": False,
        "provider_calls_enabled": False,
        "non_claim": NON_CLAIM_TEXT,
    }


def _write_json(path: str, payload: dict) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a HackAIthon MVP bar dataset manifest summary.")
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--write", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        manifest = build_bar_dataset_manifest(args.dataset_root)
    except ValueError as exc:
        parser.error(str(exc))
    if args.write:
        _write_json(args.write, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
