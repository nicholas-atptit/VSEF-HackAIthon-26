import pytest

from src.hackaithon_mvp.model_diagnostics.registry import get_adapter
from src.hackaithon_mvp.static_evidence_loader import (
    StaticEvidenceValidationError,
    load_static_evidence,
    validate_evidence_record,
)


def test_sample_evidence_loads_and_matches_registry():
    records = load_static_evidence()
    assert len(records) >= 6
    for record in records:
        adapter = get_adapter(record["model_key"])
        metadata = adapter.to_metadata()
        assert record["model_family"] == metadata["model_family"]
        assert record["model_display_name"] == metadata["display_name"]


def test_qml_evidence_is_rejected():
    with pytest.raises(StaticEvidenceValidationError):
        validate_evidence_record(
            {
                "model_key": "qml",
                "model_family": "qml",
                "model_display_name": "Excluded",
            }
        )


def test_missing_dependency_metadata_record_is_allowed_when_static_only():
    record = {
        "model_key": "catboost",
        "model_family": "classification",
        "model_display_name": "Catboost",
        "execution_mode": "metadata_only_static_demo",
    }
    validated = validate_evidence_record(record)
    assert validated["adapter_dependency_status"] == "missing_dependency"


def test_dependency_gated_record_requires_metadata_only_mode():
    with pytest.raises(StaticEvidenceValidationError):
        validate_evidence_record(
            {
                "model_key": "bilstm",
                "model_family": "deep_learning",
                "model_display_name": "BiLSTM",
                "execution_mode": "live_demo",
            }
        )
