import pytest

from src.hackaithon_mvp.engine_runtime.engine_id import EngineIdValidationError, validate_engine_id


def test_valid_baseline_support_stack_engine_ids():
    assert validate_engine_id("classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055") == "baseline"
    assert validate_engine_id("support.model_disagreement.vn30.absolute_direction.h40.basic_scope_classification") == "support"
    assert validate_engine_id("stack.validation_topk_vote.absolute_direction.h40.feature_set_c.validation_top3") == "stack"


@pytest.mark.parametrize(
    "engine_id",
    [
        "classification.qml_model.absolute_direction.h40.feature_set_c.threshold_055",
        "classification.quantum_model.absolute_direction.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.buy.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.sell.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.hold.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.trade.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.trading.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.recommendation.h40.feature_set_c.threshold_055",
        "classification.logistic_l2.allocation_advice.h40.feature_set_c.threshold_055",
    ],
)
def test_invalid_qml_quantum_and_public_action_ids_rejected(engine_id):
    with pytest.raises(EngineIdValidationError):
        validate_engine_id(engine_id)
