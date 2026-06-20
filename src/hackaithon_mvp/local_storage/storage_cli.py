"""CLI for the local HackAIthon MVP storage adapter."""

from __future__ import annotations

import argparse
import json
import sys

from .availability_index import build_availability_index
from .parquet_adapter import detect_parquet_capability, read_dataset_records, write_dataset_records


DEMO_RECORDS = (
    {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": "2026-06-18T00:00:00+07:00",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1000.0,
    },
    {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": "2026-06-19T00:00:00+07:00",
        "open": 101.0,
        "high": 103.0,
        "low": 100.0,
        "close": 102.0,
        "volume": 1100.0,
    },
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or exercise local MVP storage adapter.")
    parser.add_argument("--capability", action="store_true")
    parser.add_argument("--demo-write", action="store_true")
    parser.add_argument("--demo-read", action="store_true")
    parser.add_argument("--root", default=None)
    return parser


def _require_root(parser: argparse.ArgumentParser, root: str | None) -> str:
    if not root:
        parser.error("--root is required for demo storage operations")
    return str(root)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    selected = sum(bool(value) for value in (args.capability, args.demo_write, args.demo_read))
    if selected != 1:
        parser.error("select exactly one of --capability, --demo-write, or --demo-read")
    if args.capability:
        print(json.dumps(detect_parquet_capability(), indent=2, sort_keys=True))
        return 0
    root = _require_root(parser, args.root)
    if args.demo_write:
        result = write_dataset_records(
            root,
            "market_bars",
            DEMO_RECORDS,
            ticker="VCB",
            timeframe="1d",
            date="2026-06-19",
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    records = read_dataset_records(root, "market_bars", ticker="VCB", timeframe="1d", date="2026-06-19")
    output = {
        "read_row_count": len(records),
        "availability_index": build_availability_index(records),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
