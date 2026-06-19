import json
import re

from src.hackaithon_mvp.forecast_diagnostic_engine import NON_CLAIM_TEXT, run_forecast_diagnostic


FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "trading signal",
    "investment advice",
    "portfolio allocation advice",
)


def _engine_result(status="completed", claim_scope="diagnostic_only"):
    return {
        "engine_id": "classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055",
        "status": status,
        "diagnostic_label": "neutral_or_uncertain",
        "confidence": 0.25,
        "metrics": {},
        "claim_scope": claim_scope,
        "warnings": [],
        "metadata": {
            "model_key": "logistic_l2",
            "model_family": "classification",
            "target": "absolute_direction",
            "horizon": 40,
        },
    }


def _evidence(**metrics):
    return {
        "record_id": "demo-vcb-logistic-l2",
        "ticker": "VCB",
        "model_key": "logistic_l2",
        "model_family": "classification",
        "target": "absolute_direction",
        "horizon": 40,
        **metrics,
    }


def _assert_no_forbidden_public_terms(payload):
    text = json.dumps(payload, sort_keys=True).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert not re.search(rf"\b{re.escape(term)}\b", text), term


def test_missing_evidence_maps_to_insufficient_evidence():
    output = run_forecast_diagnostic(_engine_result(), evidence_record=None)
    assert output["forecast_diagnostic"] == "insufficient_evidence"
    assert output["evidence_status"] == "missing_evidence"


def test_skipped_engine_result_maps_to_insufficient_evidence():
    output = run_forecast_diagnostic(
        _engine_result(status="skipped_missing_evidence"),
        evidence_record=_evidence(accuracy=0.6, baseline_accuracy=0.55),
    )
    assert output["forecast_diagnostic"] == "insufficient_evidence"


def test_exploratory_claim_maps_to_exploratory_only():
    output = run_forecast_diagnostic(
        _engine_result(claim_scope="exploratory_only"),
        evidence_record=_evidence(accuracy=0.6, baseline_accuracy=0.55),
        baseline_summary={"baseline_accuracy": 0.55},
    )
    assert output["forecast_diagnostic"] == "exploratory_only"
    assert output["evidence_status"] == "exploratory_only"


def test_below_baseline_metric_maps_to_negative_bias():
    output = run_forecast_diagnostic(
        _engine_result(),
        evidence_record=_evidence(balanced_accuracy=0.51, baseline_balanced_accuracy=0.53),
        baseline_summary={"baseline_balanced_accuracy": 0.53},
    )
    assert output["forecast_diagnostic"] == "negative_bias"
    assert output["baseline_status"] == "below_baseline"


def test_weak_edge_maps_to_neutral_or_uncertain():
    output = run_forecast_diagnostic(
        _engine_result(),
        evidence_record=_evidence(accuracy=0.536, baseline_accuracy=0.53),
        baseline_summary={"baseline_accuracy": 0.53},
    )
    assert output["forecast_diagnostic"] == "neutral_or_uncertain"
    assert output["baseline_status"] == "weak_edge"


def test_meaningful_edge_maps_to_positive_bias():
    output = run_forecast_diagnostic(
        _engine_result(),
        evidence_record=_evidence(accuracy=0.56, baseline_accuracy=0.53, coverage=1.0, sample_count=250),
        baseline_summary={"baseline_accuracy": 0.53},
    )
    assert output["forecast_diagnostic"] == "positive_bias"
    assert output["baseline_status"] == "meaningful_edge"
    assert output["metric_snapshot"]["sample_count"] == 250


def test_missing_baseline_caps_confidence_and_requires_human_review():
    output = run_forecast_diagnostic(
        _engine_result(),
        evidence_record=_evidence(accuracy=0.56, baseline_accuracy=0.53),
        baseline_summary={},
    )
    assert output["confidence"] <= 0.5
    assert output["human_review_required"] is True
    assert output["non_claim"] == NON_CLAIM_TEXT


def test_forecast_diagnostic_output_has_no_forbidden_action_language():
    output = run_forecast_diagnostic(
        _engine_result(),
        evidence_record=_evidence(accuracy=0.56, baseline_accuracy=0.53),
        baseline_summary={"baseline_accuracy": 0.53},
    )
    _assert_no_forbidden_public_terms(output)


def test_forecast_diagnostic_preserves_timeframe_from_metadata_sources():
    output = run_forecast_diagnostic(
        _engine_result(),
        evidence_record=_evidence(accuracy=0.56, baseline_accuracy=0.53),
        adapter_metadata={"timeframe": "1 ngày"},
        baseline_summary={"baseline_accuracy": 0.53},
    )
    assert output["timeframe"] == "1d"
