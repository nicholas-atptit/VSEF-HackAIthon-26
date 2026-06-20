"""Hybrid storage architecture contract for the HackAIthon MVP."""

from __future__ import annotations

import argparse
import json
from typing import Any


HYBRID_ARCHITECTURE_NAME = "hybrid_storage_architecture"
HYBRID_LAYER_NAMES = (
    "canonical_data_lake",
    "metadata_store",
    "analytical_query_adapter",
    "serving_layer_optional",
)
CANONICAL_DATA_LAKE_TABLES = (
    "market_bars",
    "features",
    "forecast_outputs",
    "actual_outcomes",
    "evaluation_metrics",
    "dag_runs",
)
METADATA_STORE_TABLES = (
    "run_registry",
    "engine_registry",
    "dataset_manifest",
    "data_availability",
    "review_state",
    "audit_log",
    "policy_registry",
)
ANALYTICAL_QUERY_USE_CASES = (
    "walk_forward_evaluation",
    "top_k_diagnostics",
    "forecast_vs_actual_evaluation",
    "multi_timeframe_scans",
    "policy_optimization",
)
OPTIONAL_SERVING_TABLES = (
    "dashboard_aggregates",
    "report_query_acceleration",
    "api_read_models",
)
DEPLOYMENT_MODES = (
    "local_development",
    "single_server",
    "containerized_server",
    "cloud_object_storage",
    "cloud_metadata_db",
    "optional_cloud_serving_layer",
)
MIGRATION_PATH = (
    "local partitioned file dataset",
    "local analytical adapter",
    "metadata store contract",
    "object storage data lake",
    "lakehouse table management",
    "optional serving layer",
)
NON_CLAIM_TEXT = "Architecture contract only; local diagnostic research boundary applies."
CLAIM_BOUNDARY = {
    "local_storage_adapter_implemented": True,
    "server_database_created": False,
    "serving_database_created": False,
    "data_gateway_created": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_enabled": False,
    "inference_enabled": False,
    "benchmark_rerun": False,
    "human_review_required": True,
}
RECOMMENDED_CURRENT = "local_partitioned_file_adapter"
RECOMMENDED_TARGET = HYBRID_ARCHITECTURE_NAME


def _layer(name: str, current: tuple[str, ...], future: tuple[str, ...], stores: tuple[str, ...]) -> dict[str, Any]:
    return {
        "layer_name": name,
        "current": list(current),
        "future_compatible": list(future),
        "stores": list(stores),
    }


def get_hybrid_storage_architecture() -> dict:
    """Return the compact target storage architecture contract."""

    data_lake = _layer(
        "canonical_data_lake",
        ("local partitioned file dataset through local_storage",),
        ("object storage", "lakehouse table management later"),
        CANONICAL_DATA_LAKE_TABLES,
    )
    metadata_store = _layer(
        "metadata_store",
        ("contract only in this MVP",),
        ("server database later",),
        METADATA_STORE_TABLES,
    )
    analytical_query_adapter = {
        "layer_name": "analytical_query_adapter",
        "current": [
            "local analytical file reads through local adapter",
            "DuckDB-compatible design boundary",
        ],
        "future_compatible": ["server or cloud analytical query adapter"],
        "used_for": list(ANALYTICAL_QUERY_USE_CASES),
    }
    serving_layer_optional = {
        "layer_name": "serving_layer_optional",
        "current": ["not instantiated"],
        "future_optional": list(OPTIONAL_SERVING_TABLES),
        "serving_database_created": False,
    }
    return {
        "architecture_name": HYBRID_ARCHITECTURE_NAME,
        "recommended_current": RECOMMENDED_CURRENT,
        "recommended_target": RECOMMENDED_TARGET,
        "layers": list(HYBRID_LAYER_NAMES),
        "data_lake": data_lake,
        "metadata_store": metadata_store,
        "analytical_query_adapter": analytical_query_adapter,
        "serving_layer_optional": serving_layer_optional,
        "deployment_modes": list(DEPLOYMENT_MODES),
        "migration_path": list(MIGRATION_PATH),
        "implementation_status": {
            **dict(CLAIM_BOUNDARY),
            "serving_layer_optional_later": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def map_diagnostic_components_to_storage() -> dict:
    """Map MVP diagnostic components to storage roles without instantiating storage."""

    return {
        "component_count": 15,
        "mappings": {
            "static_evidence_loader": ["local_storage", "canonical_data_lake"],
            "engine_runtime": ["engine_registry", "run_registry"],
            "forecast_diagnostic_engine": ["forecast_outputs"],
            "quant_core_policy_runtime": ["policy_registry", "forecast_outputs"],
            "scenario_engine": ["dag_runs", "chain_outputs"],
            "risk_governance_engine": ["audit_log", "risk_flags"],
            "decision_lane_engine": ["review_state", "chain_outputs"],
            "market_context_engine": ["context_snapshots_later"],
            "calibration_engine": ["calibration_outputs"],
            "research_allocation_view": ["research_sizing_outputs"],
            "phase_router": ["routing_outputs", "review_state"],
            "evidence_packet": ["evidence_packets"],
            "diagnostic_report": ["diagnostic_reports"],
            "forecast_vs_actual_evaluation": ["actual_outcomes", "evaluation_metrics"],
            "diagnostic_dag_runtime": ["dag_runs", "audit_log"],
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def compare_storage_options() -> dict:
    """Compare local and target storage roles for staged MVP evolution."""

    options = {
        "local_partitioned_file_adapter": {
            "role": "current local file dataset adapter",
            "local_mvp_fit": "high",
            "server_fit": "medium",
            "cloud_scale_fit": "medium",
            "complexity": "low",
            "current_status": "implemented",
            "recommended_phase": "current",
        },
        "lakehouse_target": {
            "role": "future canonical data lake table layer",
            "local_mvp_fit": "medium",
            "server_fit": "high",
            "cloud_scale_fit": "high",
            "complexity": "high",
            "current_status": "contract_only",
            "recommended_phase": "later",
        },
        "metadata_store_server_db": {
            "role": "future run and review metadata store",
            "local_mvp_fit": "medium",
            "server_fit": "high",
            "cloud_scale_fit": "high",
            "complexity": "medium",
            "current_status": "not_created",
            "recommended_phase": "contract_next",
        },
        "serving_layer_optional": {
            "role": "optional read model acceleration layer",
            "local_mvp_fit": "low",
            "server_fit": "medium",
            "cloud_scale_fit": "high",
            "complexity": "very_high",
            "current_status": "not_created",
            "recommended_phase": "optional_later",
        },
        "hybrid_target": {
            "role": "combined data lake, metadata, analytical, and optional serving architecture",
            "local_mvp_fit": "medium",
            "server_fit": "high",
            "cloud_scale_fit": "high",
            "complexity": "high",
            "current_status": "contract_only",
            "recommended_phase": "target",
        },
    }
    return {
        "options": options,
        "option_count": len(options),
        "ratings": ["low", "medium", "high", "very_high"],
        "recommended_current": RECOMMENDED_CURRENT,
        "recommended_target": RECOMMENDED_TARGET,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show the HackAIthon MVP hybrid storage architecture contract.")
    parser.add_argument("--section", choices=("architecture", "component-map", "options", "all"), default="architecture")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.section == "architecture":
        output = get_hybrid_storage_architecture()
    elif args.section == "component-map":
        output = map_diagnostic_components_to_storage()
    elif args.section == "options":
        output = compare_storage_options()
    else:
        output = {
            "architecture": get_hybrid_storage_architecture(),
            "component_map": map_diagnostic_components_to_storage(),
            "options": compare_storage_options(),
        }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
