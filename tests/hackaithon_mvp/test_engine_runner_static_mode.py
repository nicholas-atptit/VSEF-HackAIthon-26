from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine
from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec


def _baseline_spec(horizon=40):
    return EngineSpec(
        engine_id=f"classification.logistic_l2.absolute_direction.h{horizon}.feature_set_c.threshold_055",
        engine_type="baseline",
        model_key="logistic_l2",
        model_family="classification",
        target="absolute_direction",
        horizon=horizon,
        feature_set="feature_set_c",
        policy="threshold_055",
        split_policy="validation_final_locked",
        run_mode="static_evidence_mvp",
        dependencies=(),
        claim_scope="diagnostic_only",
        metadata={},
    )


def test_engine_runner_completes_static_evidence_baseline():
    result = run_engine(_baseline_spec())
    assert result.status == "completed"
    assert result.metrics["matched_static_records"] >= 1


def test_engine_runner_skips_missing_static_evidence():
    result = run_engine(_baseline_spec(horizon=1))
    assert result.status == "skipped_missing_evidence"
    assert result.claim_scope == "evidence_insufficient"


def test_support_runner_skips_missing_dependency_outputs():
    spec = EngineSpec(
        engine_id="support.model_disagreement.vn30.absolute_direction.h40.basic_scope_classification",
        engine_type="support",
        model_key=None,
        model_family="classification",
        target="absolute_direction",
        horizon=40,
        feature_set="basic_scope",
        policy="model_disagreement",
        split_policy="validation_final_locked",
        run_mode="static_evidence_mvp",
        dependencies=("classification.absolute_direction.h40.basic_scope",),
        claim_scope="diagnostic_only",
        metadata={},
    )
    result = run_engine(spec)
    assert result.status == "skipped_missing_dependency"


def test_stack_runner_skips_missing_dependency_outputs():
    spec = EngineSpec(
        engine_id="stack.validation_topk_vote.absolute_direction.h40.feature_set_c.validation_top3",
        engine_type="stack",
        model_key=None,
        model_family="ensemble_regime",
        target="absolute_direction",
        horizon=40,
        feature_set="feature_set_c",
        policy="requires_support_outputs",
        split_policy="validation_final_locked",
        run_mode="static_evidence_mvp",
        dependencies=("support.evidence_strength.static_demo.absolute_direction.h40.feature_set_c_classification",),
        claim_scope="exploratory_only",
        metadata={},
    )
    result = run_engine(spec)
    assert result.status == "skipped_missing_dependency"
