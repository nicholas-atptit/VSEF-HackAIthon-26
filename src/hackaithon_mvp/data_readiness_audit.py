"""Data readiness audit for future database-backed HackAIthon MVP execution."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.data_contracts import (
    DEFAULT_TICKERS,
    build_timeframe_requirements,
)
from src.hackaithon_mvp.storage_contract import InMemoryMarketDataStore, MarketDataStore
from src.hackaithon_mvp.storage_design import get_storage_design
from src.hackaithon_mvp.timeframe_schema import REQUIRED_TIMEFRAME_INPUTS


AUDIT_MODE = "data_readiness_contract_only"
NON_CLAIM_TEXT = "Readiness audit only; no data access or prediction execution."
CLAIM_BOUNDARY = (
    "no database created",
    "no Data Gateway implementation",
    "no live data",
    "no provider API calls",
    "no model training",
    "no model inference",
    "no benchmark rerun",
    "no performance claim",
)
MISSING_SAMPLE_LIMIT = 10


def _summary_bucket() -> dict[str, int]:
    return {"requirements": 0, "ready": 0, "missing": 0}


def _ratio(ready_count: int, requirements_count: int) -> float:
    if requirements_count == 0:
        return 0.0
    return round(ready_count / requirements_count, 6)


def run_data_readiness_audit(
    store: MarketDataStore,
    tickers: tuple[str, ...] | None = None,
    timeframe_inputs: tuple[str, ...] | None = None,
    cases_per_pair: int = 10_000,
    lookback_bars: int = 120,
    safety_margin_bars: int = 100,
) -> dict:
    selected_tickers = tickers or DEFAULT_TICKERS
    selected_timeframes = timeframe_inputs or REQUIRED_TIMEFRAME_INPUTS
    requirements = build_timeframe_requirements(
        selected_tickers,
        selected_timeframes,
        cases_per_pair=cases_per_pair,
        lookback_bars=lookback_bars,
        safety_margin_bars=safety_margin_bars,
    )

    ready_count = 0
    missing_sample: list[dict[str, Any]] = []
    per_timeframe: dict[str, dict[str, int]] = {}
    per_ticker: dict[str, dict[str, int]] = {}

    for requirement in requirements:
        available_bars = int(store.get_available_bars(requirement.ticker, requirement.canonical_timeframe))
        ready = available_bars >= requirement.required_bars
        if ready:
            ready_count += 1
        timeframe_bucket = per_timeframe.setdefault(requirement.canonical_timeframe, _summary_bucket())
        ticker_bucket = per_ticker.setdefault(requirement.ticker, _summary_bucket())
        for bucket in (timeframe_bucket, ticker_bucket):
            bucket["requirements"] += 1
            bucket["ready" if ready else "missing"] += 1
        if not ready and len(missing_sample) < MISSING_SAMPLE_LIMIT:
            missing_sample.append(
                {
                    "ticker": requirement.ticker,
                    "timeframe": requirement.canonical_timeframe,
                    "required_bars": requirement.required_bars,
                    "available_bars": available_bars,
                    "shortfall_bars": max(0, requirement.required_bars - available_bars),
                }
            )

    requirements_count = len(requirements)
    missing_count = requirements_count - ready_count
    storage_design = get_storage_design()
    return {
        "audit_mode": AUDIT_MODE,
        "tickers_count": len(selected_tickers),
        "timeframes_count": len(selected_timeframes),
        "cases_per_pair": int(cases_per_pair),
        "expected_prediction_cases": len(selected_tickers) * len(selected_timeframes) * int(cases_per_pair),
        "requirements_count": requirements_count,
        "ready_count": ready_count,
        "missing_count": missing_count,
        "coverage_ratio": _ratio(ready_count, requirements_count),
        "missing_requirements_sample": missing_sample,
        "per_timeframe_summary": per_timeframe,
        "per_ticker_summary": per_ticker,
        "database_required": True,
        "data_gateway_required_later": True,
        "storage_design": storage_design,
        "database_created": storage_design["database_created"],
        "data_gateway_created": storage_design["data_gateway_created"],
        "canonical_data_format": storage_design["canonical_data_format"],
        "planned_query_adapter": storage_design["planned_query_adapter"],
        "claim_boundary": list(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "store_description": store.describe(),
        "requirement_formula": "cases_required + lookback_bars + horizon_steps + safety_margin_bars",
        "requirements_are_summarized": True,
    }


def _demo_store(fill_bars: int | None, requirements: tuple[Any, ...]) -> InMemoryMarketDataStore:
    store = InMemoryMarketDataStore()
    if fill_bars is None:
        return store
    for requirement in requirements:
        store.set_available_bars(requirement.ticker, requirement.canonical_timeframe, fill_bars)
    return store


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the HackAIthon MVP data readiness contract audit.")
    parser.add_argument("--cases-per-pair", type=int, default=10_000)
    parser.add_argument("--lookback-bars", type=int, default=120)
    parser.add_argument("--safety-margin-bars", type=int, default=100)
    parser.add_argument("--demo-fill-bars", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    requirements = build_timeframe_requirements(
        DEFAULT_TICKERS,
        REQUIRED_TIMEFRAME_INPUTS,
        cases_per_pair=args.cases_per_pair,
        lookback_bars=args.lookback_bars,
        safety_margin_bars=args.safety_margin_bars,
    )
    store = _demo_store(args.demo_fill_bars, requirements)
    audit = run_data_readiness_audit(
        store,
        cases_per_pair=args.cases_per_pair,
        lookback_bars=args.lookback_bars,
        safety_margin_bars=args.safety_margin_bars,
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
