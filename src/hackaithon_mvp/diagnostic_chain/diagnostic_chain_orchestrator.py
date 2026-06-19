"""CLI orchestrator for the 8-layer diagnostic decision chain."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .calibration_engine import run_calibration
from .chain_schema import DiagnosticChainOutput, NON_CLAIM_TEXT, assert_no_forbidden_public_terms
from .decision_lane_engine import run_decision_lane
from .market_context_engine import run_market_context
from .phase_router import run_phase_router
from .portfolio_diagnostic_allocator import run_portfolio_diagnostic_allocator
from .quant_core_engine import run_quant_core
from .review_cycle_engine import run_review_cycle
from .risk_governance_engine import run_risk_governance
from .scenario_engine import run_scenario_engine


def run_diagnostic_chain(ticker: str, sample_size: int = 500) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    quant_output = run_quant_core(normalized_ticker, sample_size=sample_size)
    scenario_output = run_scenario_engine(quant_output)
    risk_output = run_risk_governance(quant_output, scenario_output)
    decision_output = run_decision_lane(quant_output, scenario_output, risk_output)
    market_context_output = run_market_context(normalized_ticker)
    calibration_output = run_calibration(quant_output, scenario_output, risk_output, decision_output)
    review_cycle_output = run_review_cycle(
        {
            "layer_1_quant_core": quant_output,
            "layer_2_scenario": scenario_output,
            "layer_3_risk_governance": risk_output,
            "layer_4_decision_lane": decision_output,
            "layer_5_market_context": market_context_output,
            "layer_6_calibration": calibration_output,
        }
    )
    allocator_output = run_portfolio_diagnostic_allocator(decision_output, risk_output, calibration_output)
    router_output = run_phase_router(decision_output, risk_output, allocator_output)

    chain_output = DiagnosticChainOutput(
        ticker=normalized_ticker,
        layer_1_quant_core=quant_output,
        layer_2_scenario=scenario_output,
        layer_3_risk_governance=risk_output,
        layer_4_decision_lane=decision_output,
        layer_5_market_context=market_context_output,
        layer_6_calibration=calibration_output,
        review_cycle=review_cycle_output,
        layer_7_portfolio_diagnostic_allocator=allocator_output,
        layer_8_phase_router=router_output,
        non_claim=NON_CLAIM_TEXT,
    ).to_dict()
    assert_no_forbidden_public_terms(chain_output)
    return chain_output


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the HackAIthon MVP diagnostic decision chain.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--sample-size", type=int, default=500)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    output = run_diagnostic_chain(args.ticker, sample_size=args.sample_size)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
