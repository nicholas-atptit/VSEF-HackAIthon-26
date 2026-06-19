"""Layer 5: static market context placeholder."""

from __future__ import annotations

from .chain_schema import MarketContextOutput, NON_CLAIM_TEXT, assert_no_forbidden_public_terms


def run_market_context(ticker: str) -> MarketContextOutput:
    output: MarketContextOutput = {
        "market_context_status": "static_placeholder",
        "context_label": "local_context_unavailable",
        "context_notes": [
            f"{ticker.strip().upper()} context is not fetched in this MVP slice.",
            "No scraping, live social listening, or provider access is enabled.",
            "Human reviewer may attach context outside this automated run.",
        ],
        "live_context_enabled": False,
        "non_claim": NON_CLAIM_TEXT,
    }
    assert_no_forbidden_public_terms(output)
    return output
