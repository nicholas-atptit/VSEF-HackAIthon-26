"""Manual static review cycle marker for diagnostic chain runs."""

from __future__ import annotations

from datetime import datetime, timezone

from .chain_schema import ReviewCycleOutput, assert_no_forbidden_public_terms


def run_review_cycle(layer_outputs: dict) -> ReviewCycleOutput:
    output: ReviewCycleOutput = {
        "cycle_mode": "manual_static_review",
        "layers_completed": list(layer_outputs.keys()),
        "non_realtime_claim": "Manual static review cycle only; no continuous automation claim.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert_no_forbidden_public_terms(output)
    return output
