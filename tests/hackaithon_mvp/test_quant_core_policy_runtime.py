from src.hackaithon_mvp.quant_core_policy_registry import get_demo_policy_predicted_vs_actual
from src.hackaithon_mvp.quant_core_policy_runtime import (
    apply_registered_policy_to_forecast,
    convert_registered_policy_to_gate_policy,
)


def test_runtime_preserves_directional_label_for_eligible_group():
    policy = get_demo_policy_predicted_vs_actual()
    row = {
        "ticker": "AAA",
        "timeframe": "1h",
        "horizon_steps": 40,
        "model_family": "tree_a",
        "forecast_diagnostic": "positive_bias",
    }

    output = apply_registered_policy_to_forecast(row, policy)

    assert output["forecast_diagnostic"] == "positive_bias"
    assert output["pre_policy_forecast_diagnostic"] == "positive_bias"
    assert output["policy_runtime_status"] == "directional_allowed"
    assert output["policy_runtime_reason"] == "matched_eligible_group"


def test_runtime_downgrades_directional_label_for_non_eligible_group():
    policy = get_demo_policy_predicted_vs_actual()
    row = {
        "ticker": "ZZZ",
        "timeframe": "1h",
        "horizon_steps": 40,
        "model_family": "tree_a",
        "forecast_diagnostic": "negative_bias",
    }

    output = apply_registered_policy_to_forecast(row, policy)

    assert output["forecast_diagnostic"] == "neutral_or_uncertain"
    assert output["pre_policy_forecast_diagnostic"] == "negative_bias"
    assert output["policy_runtime_status"] == "downgraded_to_uncertain"
    assert output["policy_runtime_reason"] == "no_matching_eligible_group"


def test_runtime_never_upgrades_neutral_label_and_attaches_policy_metrics():
    policy = get_demo_policy_predicted_vs_actual()
    row = {
        "ticker": "AAA",
        "timeframe": "1h",
        "horizon_steps": 40,
        "model_family": "tree_a",
        "forecast_diagnostic": "neutral_or_uncertain",
    }

    output = apply_registered_policy_to_forecast(row, policy)

    assert output["forecast_diagnostic"] == "neutral_or_uncertain"
    assert output["pre_policy_forecast_diagnostic"] == "neutral_or_uncertain"
    assert output["policy_runtime_status"] == "non_directional_preserved"
    assert output["policy_validation_accuracy"] == 0.534888
    assert output["policy_validation_balanced_accuracy"] == 0.532707
    assert output["policy_validation_coverage"] == 0.16269


def test_registered_policy_converts_to_gate_policy():
    converted = convert_registered_policy_to_gate_policy(get_demo_policy_predicted_vs_actual())

    assert converted["conversion_status"] == "converted"
    assert converted["policy"]["eligible_group_count"] == 2
    assert converted["warnings"] == []
