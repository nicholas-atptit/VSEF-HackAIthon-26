from src.hackaithon_mvp.quant_core_performance_attribution import build_performance_attribution


def _row(ticker, diagnostic, actual, *, index, model_family="mf", timeframe="1h", horizon_steps=40):
    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "prediction_timestamp": f"2026-01-01T{index:02d}:00:00",
        "horizon_steps": horizon_steps,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 1.0 if actual == "positive" else -1.0,
        "actual_direction_label": actual,
        "model_family": model_family,
    }


def _perfect_group(ticker, start):
    rows = []
    for offset in range(20):
        rows.append(_row(ticker, "positive_bias", "positive", index=start + offset))
    for offset in range(20, 40):
        rows.append(_row(ticker, "negative_bias", "negative", index=start + offset))
    return rows


def _weak_group(ticker, start):
    rows = []
    for offset in range(20):
        rows.append(_row(ticker, "positive_bias", "negative", index=start + offset))
    for offset in range(20, 40):
        rows.append(_row(ticker, "negative_bias", "positive", index=start + offset))
    return rows


def test_attribution_calculates_group_metrics_and_detects_strong_and_weak_groups():
    rows = tuple(_perfect_group("AAA", 0) + _weak_group("BBB", 50))

    attribution = build_performance_attribution(rows, group_fields=("ticker",), min_sample_count=30)

    assert attribution["rows_total"] == 80
    assert attribution["eligible_directional_rows"] == 80
    assert len(attribution["strong_groups"]) == 1
    assert len(attribution["weak_groups"]) == 1
    strong = attribution["strong_groups"][0]
    weak = attribution["weak_groups"][0]
    assert strong["group_key"] == {"ticker": "AAA"}
    assert strong["directional_accuracy"] == 1.0
    assert strong["balanced_directional_accuracy"] == 1.0
    assert strong["positive_precision"] == 1.0
    assert strong["negative_precision"] == 1.0
    assert strong["positive_recall"] == 1.0
    assert strong["negative_recall"] == 1.0
    assert weak["group_key"] == {"ticker": "BBB"}
    assert weak["balanced_directional_accuracy"] == 0.0
    assert weak["is_directionally_eligible"] is False


def test_insufficient_sample_group_is_not_eligible():
    rows = tuple(_perfect_group("AAA", 0)[:10])

    attribution = build_performance_attribution(rows, group_fields=("ticker",), min_sample_count=30)

    group = attribution["groups"][0]
    assert group["sample_count"] == 10
    assert group["is_sample_sufficient"] is False
    assert group["is_directionally_eligible"] is False
    assert attribution["warnings"]["insufficient_sample_group"] == 1
