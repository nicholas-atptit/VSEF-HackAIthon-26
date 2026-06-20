import json
import re

from src.hackaithon_mvp.forecast_actual_evaluation import (
    evaluate_forecast_vs_actual,
    render_forecast_actual_report,
)

from forecast_actual_fixtures import forecast_actual_rows


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


def test_evaluation_json_has_no_forbidden_public_terms():
    evaluation = evaluate_forecast_vs_actual(forecast_actual_rows(), top_k=2)
    _assert_no_forbidden_terms(json.dumps(evaluation, sort_keys=True))


def test_evaluation_report_has_no_forbidden_public_terms():
    evaluation = evaluate_forecast_vs_actual(forecast_actual_rows(), top_k=2)
    report = render_forecast_actual_report(evaluation)
    _assert_no_forbidden_terms(report)
