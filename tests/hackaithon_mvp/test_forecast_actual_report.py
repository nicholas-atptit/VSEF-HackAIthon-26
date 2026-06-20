from src.hackaithon_mvp.forecast_actual_evaluation import (
    evaluate_forecast_vs_actual,
    render_forecast_actual_report,
)

from forecast_actual_fixtures import forecast_actual_rows


REQUIRED_SECTIONS = (
    "# HackAIthon MVP Forecast Actual Evaluation",
    "## Data Status",
    "## Scope",
    "## Overall Accuracy",
    "## Coverage and Abstention",
    "## By Timeframe",
    "## By Ticker",
    "## By Model Family",
    "## Top-K Summary",
    "## Claim Boundary",
)


def test_report_renderer_includes_required_sections():
    evaluation = evaluate_forecast_vs_actual(forecast_actual_rows(), top_k=2)
    report = render_forecast_actual_report(evaluation)

    for section in REQUIRED_SECTIONS:
        assert section in report
    assert "Directional accuracy: 0.5" in report


def test_report_renderer_handles_missing_actual_data():
    evaluation = evaluate_forecast_vs_actual(tuple())
    report = render_forecast_actual_report(evaluation)

    assert "Actual data status: missing" in report
    assert "Accuracy is unavailable" in report
