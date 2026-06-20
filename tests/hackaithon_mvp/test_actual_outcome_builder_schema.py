import csv
import json

import pytest

from src.hackaithon_mvp.actual_outcome_builder import (
    build_actual_outcomes,
    load_local_rows,
    render_actual_outcome_summary,
)


def _forecast(**overrides):
    row = {
        "ticker": "vcb",
        "timeframe": "1 ngày",
        "prediction_timestamp": "2026-01-01T00:00:00+07:00",
        "horizon_steps": 1,
        "forecast_diagnostic": "positive_bias",
        "engine_id": "engine-1",
        "model_key": "logistic_l2",
        "model_family": "classification",
        "diagnostic_score": "0.7",
        "confidence": "0.6",
        "route": "review",
        "risk_level": "low",
        "split_id": "validation",
        "source": "fixture",
        "policy_id": "policy-1",
        "policy_name": "demo",
        "policy_runtime_status": "applied",
    }
    row.update(overrides)
    return row


def _bar(**overrides):
    row = {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": "2026-01-01T00:00:00+07:00",
        "open": 10,
        "high": 11,
        "low": 9,
        "close": 10,
        "volume": 100,
    }
    row.update(overrides)
    return row


def test_load_local_rows_supports_csv_json_and_jsonl(tmp_path):
    rows = [_forecast()]
    csv_path = tmp_path / "rows.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    json_path = tmp_path / "rows.json"
    json_path.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    jsonl_path = tmp_path / "rows.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    assert load_local_rows(str(csv_path))[0]["ticker"] == "vcb"
    assert load_local_rows(str(json_path))[0]["ticker"] == "vcb"
    assert load_local_rows(str(jsonl_path))[0]["ticker"] == "vcb"


def test_valid_forecast_and_bar_rows_build_evaluator_row():
    rows = build_actual_outcomes(
        (_forecast(),),
        (
            _bar(),
            _bar(timestamp="2026-01-02T00:00:00+07:00", close=12, high=13, low=11, open=12),
        ),
    )

    assert rows[0]["ticker"] == "VCB"
    assert rows[0]["timeframe"] == "1d"
    assert rows[0]["engine_id"] == "engine-1"
    assert rows[0]["policy_runtime_status"] == "applied"
    assert render_actual_outcome_summary(rows)["rows_total"] == 1


def test_invalid_forecast_timeframe_is_rejected():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        build_actual_outcomes((_forecast(timeframe="3m"),), (_bar(),))


def test_invalid_ohlcv_is_rejected():
    with pytest.raises(ValueError, match="high must be greater than or equal to low"):
        build_actual_outcomes((_forecast(),), (_bar(high=8),))


def test_bar_aliases_are_supported():
    rows = build_actual_outcomes(
        (_forecast(),),
        (
            _bar(time="2026-01-01T00:00:00+07:00", frequency="1 ngày"),
            _bar(time="2026-01-02T00:00:00+07:00", frequency="1 ngày", close=9, high=10, low=8, open=9),
        ),
    )

    assert rows[0]["actual_direction_label"] == "negative"
