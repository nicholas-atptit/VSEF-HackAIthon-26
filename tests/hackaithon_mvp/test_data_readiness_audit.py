from src.hackaithon_mvp.data_contracts import DEFAULT_TICKERS
from src.hackaithon_mvp.data_readiness_audit import run_data_readiness_audit
from src.hackaithon_mvp.storage_contract import InMemoryMarketDataStore
from src.hackaithon_mvp.timeframe_schema import REQUIRED_TIMEFRAME_INPUTS, normalize_timeframe


def test_empty_store_reports_missing_data_without_code_failure():
    audit = run_data_readiness_audit(InMemoryMarketDataStore())

    assert audit["tickers_count"] == 30
    assert audit["timeframes_count"] == 18
    assert audit["requirements_count"] == 540
    assert audit["expected_prediction_cases"] == 5_400_000
    assert audit["ready_count"] == 0
    assert audit["missing_count"] == 540
    assert audit["coverage_ratio"] == 0
    assert audit["database_required"] is True
    assert audit["data_gateway_required_later"] is True


def test_demo_filled_store_reaches_full_contract_coverage_when_bars_are_enough():
    store = InMemoryMarketDataStore()
    for ticker in DEFAULT_TICKERS:
        for timeframe in REQUIRED_TIMEFRAME_INPUTS:
            store.set_available_bars(ticker, normalize_timeframe(timeframe), 20_000)

    audit = run_data_readiness_audit(store)

    assert audit["requirements_count"] == 540
    assert audit["ready_count"] == 540
    assert audit["missing_count"] == 0
    assert audit["coverage_ratio"] == 1


def test_missing_requirements_are_summarized_not_fully_dumped():
    audit = run_data_readiness_audit(InMemoryMarketDataStore())

    assert len(audit["missing_requirements_sample"]) == 10
    assert audit["requirements_are_summarized"] is True
    assert len(audit["per_timeframe_summary"]) == 18
    assert len(audit["per_ticker_summary"]) == 30


def test_data_readiness_audit_claim_boundary_disables_runtime_behaviors():
    audit = run_data_readiness_audit(InMemoryMarketDataStore())

    for boundary in (
        "no database created",
        "no Data Gateway implementation",
        "no live data",
        "no provider API calls",
        "no model training",
        "no model inference",
        "no benchmark rerun",
        "no performance claim",
    ):
        assert boundary in audit["claim_boundary"]
