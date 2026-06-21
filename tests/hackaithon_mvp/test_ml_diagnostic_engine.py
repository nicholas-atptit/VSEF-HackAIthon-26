from copy import deepcopy

from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.ml_diagnostic_engine import (
    compute_model_agreement,
    compute_signal_quality,
    run_ml_diagnostic_engine,
    validate_ml_diagnostic_records,
)


def _records():
    return tuple(build_minimal_engine_input_fixture()["model_diagnostics"])


def test_ml_diagnostic_engine_detects_agreement():
    result = run_ml_diagnostic_engine(_records())

    assert result["ml_engine_status"] == "completed"
    assert result["agreement_status"] == "strong_agreement"
    assert result["recommended_review_lane"] == "standard_human_review"
    assert result["human_review_required"] is True
    assert result["auto_execution_allowed"] is False


def test_ml_diagnostic_engine_detects_disagreement():
    records = [dict(row) for row in _records()]
    records[0]["forecast_diagnostic"] = "positive_bias"
    records[1]["forecast_diagnostic"] = "negative_bias"

    agreement = compute_model_agreement(tuple(records))
    result = run_ml_diagnostic_engine(tuple(records))

    assert agreement["agreement_status"] == "high_disagreement"
    assert result["recommended_review_lane"] == "risk_review_required"


def test_ml_diagnostic_engine_detects_insufficient_and_weak_evidence():
    records = [dict(row) for row in _records()]
    for row in records:
        row["forecast_diagnostic"] = "insufficient_evidence"
        row["coverage_ratio"] = 0.1
        row["confidence"] = 0.2

    quality = compute_signal_quality(tuple(records))
    result = run_ml_diagnostic_engine(tuple(records))

    assert quality["quality_status"] == "insufficient"
    assert result["coverage_status"] == "weak"
    assert result["recommended_review_lane"] == "evidence_insufficient_review"


def test_ml_diagnostic_validation_rejects_bad_record():
    records = list(_records())
    records[0] = deepcopy(records[0])
    records[0].pop("model_key")

    result = validate_ml_diagnostic_records(tuple(records))

    assert result["is_valid"] is False
    assert result["errors"]
