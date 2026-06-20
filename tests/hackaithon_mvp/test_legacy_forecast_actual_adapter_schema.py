import json

import pytest

from src.hackaithon_mvp.legacy_forecast_actual_adapter import (
    convert_legacy_rows_to_forecast_actual,
    load_legacy_rows,
)


def _legacy_row(**overrides):
    row = {
        "ticker": "VCB",
        "datetime": "2025-01-02",
        "horizon": "40",
        "model_id": "logistic_l2",
        "model_group": "classification",
        "split": "final",
        "y_true": "1",
        "y_pred": "1",
    }
    row.update(overrides)
    return row


def test_csv_loader_works(tmp_path):
    path = tmp_path / "legacy.csv"
    path.write_text("ticker,datetime,horizon,y_true,y_pred\nVCB,2025-01-02,40,1,0\n", encoding="utf-8")

    rows = load_legacy_rows(str(path))

    assert rows[0]["ticker"] == "VCB"
    assert rows[0]["y_pred"] == "0"


def test_json_loader_works(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"rows": [_legacy_row()]}), encoding="utf-8")

    rows = load_legacy_rows(str(path))

    assert rows[0]["model_id"] == "logistic_l2"


def test_jsonl_loader_works(tmp_path):
    path = tmp_path / "legacy.jsonl"
    path.write_text(json.dumps(_legacy_row()) + "\n", encoding="utf-8")

    rows = load_legacy_rows(str(path))

    assert len(rows) == 1


def test_missing_ticker_rejects_unless_default_is_provided():
    row = _legacy_row(ticker="")

    with pytest.raises(ValueError, match="ticker"):
        convert_legacy_rows_to_forecast_actual((row,), default_timeframe="1d")

    converted = convert_legacy_rows_to_forecast_actual((row,), default_ticker="BID", default_timeframe="1d")
    assert converted[0]["ticker"] == "BID"


def test_missing_timeframe_rejects_unless_default_or_frequency_is_provided():
    row = _legacy_row()

    with pytest.raises(ValueError, match="timeframe"):
        convert_legacy_rows_to_forecast_actual((row,))

    converted = convert_legacy_rows_to_forecast_actual((row,), default_timeframe="40d")
    assert converted[0]["timeframe"] == "40d"


def test_missing_horizon_rejects_unless_default_is_provided():
    row = _legacy_row(horizon="")

    with pytest.raises(ValueError, match="horizon_steps"):
        convert_legacy_rows_to_forecast_actual((row,), default_timeframe="1d")

    converted = convert_legacy_rows_to_forecast_actual((row,), default_timeframe="1d", default_horizon_steps=1)
    assert converted[0]["horizon_steps"] == 1


def test_missing_timestamp_rejects_unless_row_index_timestamp_allowed():
    row = _legacy_row(datetime="")

    with pytest.raises(ValueError, match="prediction_timestamp"):
        convert_legacy_rows_to_forecast_actual((row,), default_timeframe="1d")

    converted = convert_legacy_rows_to_forecast_actual(
        (row,),
        default_timeframe="1d",
        allow_row_index_timestamp=True,
    )
    assert converted[0]["prediction_timestamp"] == "row_index_0"
    assert converted[0]["synthetic_row_index_timestamp_used"] is True
