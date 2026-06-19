import pytest

from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec


def test_engine_spec_accepts_valid_baseline_contract():
    spec = EngineSpec(
        engine_id="classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055",
        engine_type="baseline",
        model_key="logistic_l2",
        model_family="classification",
        target="absolute_direction",
        horizon=40,
        feature_set="feature_set_c",
        policy="threshold_055",
        split_policy="validation_final_locked",
        run_mode="static_evidence_mvp",
        dependencies=(),
        claim_scope="diagnostic_only",
        metadata={"source": "unit_test"},
    )
    assert spec.to_dict()["engine_id"] == spec.engine_id


def test_engine_spec_rejects_type_mismatch():
    with pytest.raises(ValueError):
        EngineSpec(
            engine_id="stack.validation_topk_vote.absolute_direction.h40.feature_set_c.validation_top3",
            engine_type="baseline",
            model_key="logistic_l2",
            model_family="classification",
            target="absolute_direction",
            horizon=40,
            feature_set="feature_set_c",
            policy="threshold_055",
            split_policy="validation_final_locked",
            run_mode="static_evidence_mvp",
            dependencies=(),
            claim_scope="diagnostic_only",
            metadata={},
        )


def test_engine_spec_rejects_forbidden_metadata_terms():
    with pytest.raises(ValueError):
        EngineSpec(
            engine_id="classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055",
            engine_type="baseline",
            model_key="logistic_l2",
            model_family="classification",
            target="absolute_direction",
            horizon=40,
            feature_set="feature_set_c",
            policy="threshold_055",
            split_policy="validation_final_locked",
            run_mode="static_evidence_mvp",
            dependencies=(),
            claim_scope="diagnostic_only",
            metadata={"bad": "buy"},
        )
