from src.hackaithon_mvp.storage_design import get_storage_design


def test_storage_design_exposes_hybrid_contract_fields():
    design = get_storage_design()

    assert design["recommended_current"] == "local_partitioned_file_adapter"
    assert design["recommended_target"] == "hybrid_storage_architecture"
    assert design["hybrid_architecture_enabled"] is True
    assert design["hybrid_architecture_module"] == "src.hackaithon_mvp.hybrid_storage_architecture"
    assert design["storage_target_architecture"] == "hybrid_storage_architecture"
    assert design["local_storage_adapter_implemented"] is True
    assert design["server_database_created"] is False
    assert design["data_gateway_created"] is False
    assert design["live_data_enabled"] is False
    assert design["provider_calls_enabled"] is False
