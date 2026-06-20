from src.hackaithon_mvp.quant_core_policy_registry import (
    build_policy_registry_entry,
    get_demo_policy_h40_direction_only,
    get_demo_policy_predicted_vs_actual,
    validate_policy_registry_entry,
)


def test_policy_registry_entry_validates():
    policy = build_policy_registry_entry(
        policy_id="policy.demo",
        policy_name="eligible_slice_gate",
        policy_type="eligible_slice_gate",
        source_dataset_id="local_validation_split",
        validation_accuracy=0.6,
        validation_balanced_accuracy=0.58,
        validation_coverage=0.4,
        eligible_groups=({"ticker": "AAA", "timeframe": "1h"},),
    )

    validation = validate_policy_registry_entry(policy)

    assert validation["is_valid"] is True
    assert validation["errors"] == []
    assert policy["eligible_group_count"] == 1
    assert policy["claim_boundary"]["not_training_result"] is True
    assert policy["claim_boundary"]["not_inference_result"] is True
    assert policy["claim_boundary"]["not_benchmark_rerun"] is True


def test_invalid_policy_is_rejected():
    validation = validate_policy_registry_entry(
        {
            "policy_id": "",
            "eligible_groups": "not-a-list",
            "validation_metrics": {"validation_accuracy": "x", "validation_coverage": 0},
        }
    )

    assert validation["is_valid"] is False
    assert validation["errors"]


def test_demo_predicted_vs_actual_policy_has_reported_metrics_and_low_coverage_warning():
    policy = get_demo_policy_predicted_vs_actual()

    assert policy["validation_metrics"]["validation_accuracy"] == 0.534888
    assert policy["validation_metrics"]["validation_balanced_accuracy"] == 0.532707
    assert policy["validation_metrics"]["validation_coverage"] == 0.16269
    assert "large_coverage_reduction" in policy["warnings"]
    assert validate_policy_registry_entry(policy)["is_valid"] is True


def test_demo_h40_policy_has_reported_metrics_and_direction_only_warning():
    policy = get_demo_policy_h40_direction_only()

    assert policy["validation_metrics"]["validation_accuracy"] == 0.738202
    assert policy["validation_metrics"]["validation_balanced_accuracy"] == 0.68537
    assert policy["validation_metrics"]["validation_coverage"] == 0.546012
    assert "direction_only_legacy_evidence" in policy["warnings"]
    assert validate_policy_registry_entry(policy)["is_valid"] is True
