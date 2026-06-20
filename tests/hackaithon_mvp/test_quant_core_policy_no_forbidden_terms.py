import json
import re

from src.hackaithon_mvp.quant_core_policy_registry import (
    get_demo_policy_h40_direction_only,
    get_demo_policy_predicted_vs_actual,
)
from src.hackaithon_mvp.quant_core_policy_runtime import apply_registered_policy_to_forecast


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\bfinancial advice\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bdeployment\b",
    r"\bapproval\b",
    r"\bclient relationship\b",
)


def _assert_no_forbidden_terms(payload) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, text) is None, pattern


def test_policy_registry_and_runtime_outputs_have_no_forbidden_public_terms():
    policy = get_demo_policy_predicted_vs_actual()
    output = apply_registered_policy_to_forecast(
        {
            "ticker": "AAA",
            "timeframe": "1h",
            "horizon_steps": 40,
            "model_family": "tree_a",
            "forecast_diagnostic": "positive_bias",
        },
        policy,
    )

    _assert_no_forbidden_terms({"policy": policy, "runtime": output, "h40": get_demo_policy_h40_direction_only()})


def test_policy_claim_boundary_blocks_forbidden_runtime_behaviors():
    policy = get_demo_policy_predicted_vs_actual()

    assert policy["claim_boundary"]["not_training_result"] is True
    assert policy["claim_boundary"]["not_inference_result"] is True
    assert policy["claim_boundary"]["not_benchmark_rerun"] is True
    assert policy["claim_boundary"]["human_review_required"] is True
