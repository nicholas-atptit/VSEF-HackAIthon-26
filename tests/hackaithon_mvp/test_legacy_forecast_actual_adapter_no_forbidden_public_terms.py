import json
import re

from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.legacy_forecast_actual_adapter import (
    convert_legacy_rows_to_forecast_actual,
    summarize_conversion,
)


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\bfinancial advice\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bclient relationship\b",
)


def _assert_no_forbidden_terms(text: str) -> None:
    lowered = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_adapter_summary_and_evaluation_use_no_forbidden_public_terms():
    converted = convert_legacy_rows_to_forecast_actual(
        ({"ticker": "VCB", "datetime": "2025-01-02", "horizon": "1", "y_true": "1", "y_pred": "1"},),
        default_timeframe="1d",
    )

    text = json.dumps(
        {
            "conversion_summary": summarize_conversion(converted),
            "evaluation": evaluate_forecast_vs_actual(converted),
        },
        sort_keys=True,
    )

    _assert_no_forbidden_terms(text)


def test_adapter_claim_boundary_flags_are_absent_because_no_external_work_is_performed():
    converted = convert_legacy_rows_to_forecast_actual(
        ({"ticker": "VCB", "datetime": "2025-01-02", "horizon": "1", "y_true": "1", "y_pred": "1"},),
        default_timeframe="1d",
    )
    evaluation = evaluate_forecast_vs_actual(converted)

    assert evaluation["claim_boundary"]["no_live_data"] is True
    assert evaluation["claim_boundary"]["no_provider_api_calls"] is True
    assert evaluation["claim_boundary"]["no_training"] is True
    assert evaluation["claim_boundary"]["no_inference"] is True
