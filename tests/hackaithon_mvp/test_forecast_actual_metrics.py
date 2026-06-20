from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual

from forecast_actual_fixtures import forecast_actual_rows


def test_directional_and_abstention_metrics_from_fixture():
    evaluation = evaluate_forecast_vs_actual(forecast_actual_rows())

    assert evaluation["actual_data_status"] == "provided"
    assert evaluation["rows_total"] == 7
    assert evaluation["eligible_directional_rows"] == 4
    assert evaluation["abstained_rows"] == 3
    assert evaluation["correct_directional_rows"] == 2
    assert evaluation["incorrect_directional_rows"] == 2
    assert evaluation["directional_accuracy"] == 0.5
    assert evaluation["coverage_ratio"] == round(4 / 7, 6)
    assert evaluation["abstention_ratio"] == round(3 / 7, 6)
    assert evaluation["positive_precision"] == 0.5
    assert evaluation["negative_precision"] == 0.5
    assert evaluation["balanced_directional_accuracy"] == 0.5


def test_grouped_metrics_by_timeframe_ticker_and_model_family():
    evaluation = evaluate_forecast_vs_actual(forecast_actual_rows())

    assert evaluation["by_timeframe"]["1d"]["rows_total"] == 2
    assert evaluation["by_timeframe"]["2h"]["directional_accuracy"] == 0.5
    assert evaluation["by_ticker"]["VCB"]["eligible_directional_rows"] == 2
    assert evaluation["by_ticker"]["CTG"]["abstained_rows"] == 2
    assert evaluation["by_model_family"]["classification"]["rows_total"] == 3
    assert evaluation["by_model_family"]["baseline"]["directional_accuracy"] == 0.5


def test_empty_rows_do_not_fabricate_accuracy():
    evaluation = evaluate_forecast_vs_actual(tuple())

    assert evaluation["actual_data_status"] == "missing"
    assert evaluation["directional_accuracy"] is None
    assert evaluation["coverage_ratio"] is None
    assert evaluation["claim_boundary"]["actual_data_required"] is True
