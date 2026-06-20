from src.hackaithon_mvp.data_readiness_audit import run_data_readiness_audit
from src.hackaithon_mvp.storage_contract import InMemoryMarketDataStore


def test_data_readiness_audit_includes_hybrid_storage_fields():
    audit = run_data_readiness_audit(
        InMemoryMarketDataStore(),
        tickers=("VCB",),
        timeframe_inputs=("1d",),
        cases_per_pair=5,
    )

    assert audit["coverage_ratio"] == 0
    assert audit["storage_target_architecture"] == "hybrid_storage_architecture"
    assert audit["recommended_current_storage"] == "local_partitioned_file_adapter"
    assert audit["recommended_target_storage"] == "hybrid_storage_architecture"
    assert audit["local_storage_adapter_implemented"] is True
    assert audit["server_database_required_later"] is True
    assert audit["serving_layer_optional_later"] is True
    assert audit["server_database_created"] is False
    assert audit["data_gateway_created"] is False


def test_data_readiness_audit_still_reaches_full_coverage_with_demo_store():
    store = InMemoryMarketDataStore()
    store.set_available_bars("VCB", "1d", 500)

    audit = run_data_readiness_audit(
        store,
        tickers=("VCB",),
        timeframe_inputs=("1d",),
        cases_per_pair=5,
    )

    assert audit["requirements_count"] == 1
    assert audit["ready_count"] == 1
    assert audit["coverage_ratio"] == 1
