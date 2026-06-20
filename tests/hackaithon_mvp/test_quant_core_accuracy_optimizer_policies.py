from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.quant_core_accuracy_optimizer import (
    apply_accuracy_policy,
    build_candidate_policies,
    evaluate_accuracy_policy,
    run_accuracy_optimization,
)


def _row(ticker, diagnostic, actual, index, *, score=None, model_family="mf"):
    row = {
        "ticker": ticker,
        "timeframe": "1h",
        "prediction_timestamp": f"2026-01-01T{index:02d}:00:00",
        "horizon_steps": 40,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 1.0 if actual == "positive" else -1.0,
        "actual_direction_label": actual,
        "model_family": model_family,
    }
    if score is not None:
        row["diagnostic_score"] = score
    return row


def _mixed_rows():
    rows = []
    for index in range(20):
        rows.append(_row("GOOD", "positive_bias", "positive", index))
    for index in range(20, 40):
        rows.append(_row("GOOD", "negative_bias", "negative", index))
    for index in range(40, 60):
        rows.append(_row("WEAK", "positive_bias", "negative", index))
    for index in range(60, 80):
        rows.append(_row("WEAK", "negative_bias", "positive", index))
    return tuple(rows)


def test_baseline_pass_through_equals_original_evaluation():
    rows = _mixed_rows()
    policy = build_candidate_policies(rows)[0]

    original = evaluate_forecast_vs_actual(rows)
    policy_result = evaluate_accuracy_policy(rows, policy)

    assert policy_result["directional_accuracy"] == original["directional_accuracy"]
    assert policy_result["balanced_directional_accuracy"] == original["balanced_directional_accuracy"]
    assert policy_result["coverage_ratio"] == original["coverage_ratio"]


def test_eligible_slice_gate_improves_accuracy_on_constructed_fixture():
    rows = _mixed_rows()
    policy = next(policy for policy in build_candidate_policies(rows) if policy["policy_name"] == "eligible_slice_gate_bacc_0.525")

    result = evaluate_accuracy_policy(rows, policy)

    assert result["directional_accuracy"] == 1.0
    assert result["balanced_directional_accuracy"] == 1.0
    assert result["coverage_ratio"] == 0.5


def test_strong_slice_only_increases_accuracy_while_reducing_coverage():
    rows = _mixed_rows()
    baseline = evaluate_accuracy_policy(rows, build_candidate_policies(rows)[0])
    policy = next(policy for policy in build_candidate_policies(rows) if policy["policy_name"] == "strong_slice_only")
    result = evaluate_accuracy_policy(rows, policy)

    assert result["directional_accuracy"] > baseline["directional_accuracy"]
    assert result["coverage_ratio"] < baseline["coverage_ratio"]


def test_weak_slice_abstention_downgrades_weak_groups():
    rows = _mixed_rows()
    policy = next(policy for policy in build_candidate_policies(rows) if policy["policy_name"] == "weak_slice_abstention")
    applied = apply_accuracy_policy(rows, policy)

    weak_rows = [row for row in applied if row["ticker"] == "WEAK"]
    assert all(row["forecast_diagnostic"] == "neutral_or_uncertain" for row in weak_rows)
    assert all(row["pre_policy_forecast_diagnostic"] in {"positive_bias", "negative_bias"} for row in weak_rows)


def test_neutral_labels_are_never_upgraded():
    rows = _mixed_rows() + (
        _row("GOOD", "neutral_or_uncertain", "positive", 99),
    )
    policy = next(policy for policy in build_candidate_policies(rows) if policy["policy_name"] == "strong_slice_only")
    applied = apply_accuracy_policy(rows, policy)

    assert applied[-1]["forecast_diagnostic"] == "neutral_or_uncertain"
    assert applied[-1]["accuracy_policy_reason"] == "non_directional_preserved"


def test_candidate_selection_uses_validation_not_calibration():
    rows = []
    for index in range(60):
        rows.append(_row("EARLY", "positive_bias", "positive", index))
    for index in range(60, 100):
        rows.append(_row("EARLY", "positive_bias", "negative", index))
    for index in range(100, 140):
        rows.append(_row("LATE", "positive_bias", "positive", index))

    result = run_accuracy_optimization(tuple(rows), calibration_ratio=0.6, min_validation_coverage=0.05)

    assert result["best_policy_summary"]["policy_name"] == "baseline_pass_through"
    assert "no_policy_improved_validation_balanced_directional_accuracy" in result["warnings"]


def test_coverage_threshold_prevents_trivial_near_zero_coverage_policy():
    rows = _mixed_rows()
    result = run_accuracy_optimization(rows, calibration_ratio=0.5, min_validation_coverage=0.95)

    assert result["best_policy_summary"]["policy_name"] == "baseline_pass_through"
