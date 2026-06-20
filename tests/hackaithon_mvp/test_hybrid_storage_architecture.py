from pathlib import Path

from src.hackaithon_mvp.hybrid_storage_architecture import (
    DEPLOYMENT_MODES,
    HYBRID_LAYER_NAMES,
    MIGRATION_PATH,
    get_hybrid_storage_architecture,
)


def test_repo_guard_documents_correct_active_worktree():
    cwd_text = str(Path.cwd()).replace("\\", "/")

    assert "VSEF-HackAIthon-26-mvp-worktree" not in cwd_text


def test_hybrid_architecture_returns_layers_and_safety_flags():
    architecture = get_hybrid_storage_architecture()

    assert architecture["architecture_name"] == "hybrid_storage_architecture"
    assert architecture["layers"] == list(HYBRID_LAYER_NAMES)
    assert architecture["recommended_current"] == "local_partitioned_file_adapter"
    assert architecture["recommended_target"] == "hybrid_storage_architecture"
    assert architecture["data_lake"]["stores"] == [
        "market_bars",
        "features",
        "forecast_outputs",
        "actual_outcomes",
        "evaluation_metrics",
        "dag_runs",
    ]
    assert architecture["metadata_store"]["stores"] == [
        "run_registry",
        "engine_registry",
        "dataset_manifest",
        "data_availability",
        "review_state",
        "audit_log",
        "policy_registry",
    ]

    implementation_status = architecture["implementation_status"]
    assert implementation_status["local_storage_adapter_implemented"] is True
    assert implementation_status["server_database_created"] is False
    assert implementation_status["serving_database_created"] is False
    assert implementation_status["data_gateway_created"] is False
    assert implementation_status["live_data_enabled"] is False
    assert implementation_status["provider_calls_enabled"] is False
    assert implementation_status["training_enabled"] is False
    assert implementation_status["inference_enabled"] is False


def test_deployment_modes_and_migration_path_are_ordered():
    architecture = get_hybrid_storage_architecture()

    assert set(architecture["deployment_modes"]) == set(DEPLOYMENT_MODES)
    assert {
        "local_development",
        "single_server",
        "containerized_server",
        "cloud_object_storage",
        "cloud_metadata_db",
        "optional_cloud_serving_layer",
    }.issubset(architecture["deployment_modes"])
    assert architecture["migration_path"] == list(MIGRATION_PATH)
    assert architecture["migration_path"][0] == "local partitioned file dataset"
    assert architecture["migration_path"][-1] == "optional serving layer"
