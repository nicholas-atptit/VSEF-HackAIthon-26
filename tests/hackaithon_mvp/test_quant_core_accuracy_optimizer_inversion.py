from src.hackaithon_mvp.quant_core_accuracy_optimizer import (
    apply_accuracy_policy,
    build_candidate_policies,
    build_gate_policy_from_accuracy_optimizer,
)


def _row(index, diagnostic, actual):
    return {
        "ticker": "INV",
        "timeframe": "1h",
        "prediction_timestamp": f"2026-01-01T{index:03d}:00:00",
        "horizon_steps": 40,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 1.0 if actual == "positive" else -1.0,
        "actual_direction_label": actual,
        "model_family": "mf",
    }


def test_validated_inversion_triggers_only_when_strict_conditions_are_met():
    rows = []
    for index in range(60):
        rows.append(_row(index, "positive_bias", "negative"))
    for index in range(60, 120):
        rows.append(_row(index, "negative_bias", "positive"))

    policy = next(policy for policy in build_candidate_policies(tuple(rows)) if policy["policy_name"] == "validated_inversion")
    applied = apply_accuracy_policy(tuple(rows), policy)

    assert len(policy["inversion_group_ids"]) == 1
    assert applied[0]["forecast_diagnostic"] == "negative_bias"
    assert applied[-1]["forecast_diagnostic"] == "positive_bias"
    assert applied[0]["accuracy_policy_reason"] == "validated_inversion_applied"


def test_validated_inversion_does_not_trigger_for_small_samples():
    rows = tuple(_row(index, "positive_bias", "negative") for index in range(60))

    policies = build_candidate_policies(rows)

    assert all(policy["policy_name"] != "validated_inversion" for policy in policies)


def test_gate_conversion_returns_warning_for_inversion_policy():
    rows = []
    for index in range(60):
        rows.append(_row(index, "positive_bias", "negative"))
    for index in range(60, 120):
        rows.append(_row(index, "negative_bias", "positive"))
    policy = next(policy for policy in build_candidate_policies(tuple(rows)) if policy["policy_name"] == "validated_inversion")

    converted = build_gate_policy_from_accuracy_optimizer(policy)

    assert converted["conversion_status"] == "not_convertible"
    assert converted["warnings"]
