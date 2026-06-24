from src.hackaithon_mvp.data_expanded_forecast_contract import (
    render_data_expanded_forecast_contract_report,
    validate_expanded_price_panel_schema,
)


def test_expanded_contract_reports_coverage_and_optional_context():
    rows = [
        {
            "ticker": "AAA",
            "timestamp": "2026-01-01",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10.5,
            "volume": 1000,
            "adjusted_close": 10.4,
            "index_return": 0.01,
            "sector": "banking",
        },
        {
            "ticker": "AAA",
            "timestamp": "2026-01-01",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10.5,
            "volume": 1000,
            "adjusted_close": 10.4,
            "index_return": 0.01,
            "sector": "banking",
        },
    ]

    result = validate_expanded_price_panel_schema(rows)
    report = render_data_expanded_forecast_contract_report(result)

    assert result["contract_status"] == "valid"
    assert result["missing_required_columns"] == []
    assert result["ticker_coverage"]["ticker_count"] == 1
    assert result["duplicate_timestamp_audit"]["duplicate_key_count"] == 1
    assert result["adjusted_price_availability"]["available"] is True
    assert result["market_context_availability"]["available"] is True
    assert result["sector_context_availability"]["available"] is True
    assert "Data-Expanded Forecast Contract" in report


def test_expanded_contract_blocks_missing_required_columns():
    result = validate_expanded_price_panel_schema([{"ticker": "AAA", "timestamp": "2026-01-01"}])

    assert result["contract_status"] == "invalid"
    assert "close" in result["missing_required_columns"]
