"""Diagram-to-code coverage matrix for the local architecture demo."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any


DIAGRAM_BLOCKS = (
    "data_sources",
    "quant_core",
    "scenario_engine",
    "risk_governance",
    "decision_lane",
    "market_context",
    "social_listening",
    "fine_tune_engine",
    "portfolio_allocator",
    "phase_router",
    "feedback_loop",
    "periodic_output",
    "dashboard_destination",
)
VALID_STATUSES = {
    "implemented",
    "implemented_as_contract",
    "implemented_as_local_demo",
    "partial",
    "future",
}
NON_CLAIM_TEXT = "Diagram coverage is a local research architecture map; human review remains required."
CLAIM_BOUNDARY = {
    "coverage_mapping_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}


def _row(
    *,
    diagram_block: str,
    diagram_label: str,
    mvp_status: str,
    implementation_level: str,
    implemented_modules: tuple[str, ...],
    test_files: tuple[str, ...],
    demo_command: str,
    current_boundary: str,
    future_work: str,
    claim_boundary: str,
) -> dict[str, Any]:
    if diagram_block not in DIAGRAM_BLOCKS:
        raise ValueError(f"unknown diagram block: {diagram_block}")
    if mvp_status not in VALID_STATUSES:
        raise ValueError(f"unknown MVP status: {mvp_status}")
    return {
        "diagram_block": diagram_block,
        "diagram_label": diagram_label,
        "mvp_status": mvp_status,
        "implementation_level": implementation_level,
        "implemented_modules": list(implemented_modules),
        "test_files": list(test_files),
        "demo_command": demo_command,
        "current_boundary": current_boundary,
        "future_work": future_work,
        "claim_boundary": claim_boundary,
    }


def build_diagram_coverage_matrix() -> tuple[dict, ...]:
    """Return the deterministic architecture diagram coverage matrix."""

    return (
        _row(
            diagram_block="data_sources",
            diagram_label="Data Sources",
            mvp_status="partial",
            implementation_level="local_storage_and_static_evidence_only",
            implemented_modules=(
                "src/hackaithon_mvp/static_evidence_loader.py",
                "src/hackaithon_mvp/local_storage/parquet_adapter.py",
                "src/hackaithon_mvp/data_readiness_audit.py",
            ),
            test_files=(
                "tests/hackaithon_mvp/test_static_evidence_loader.py",
                "tests/hackaithon_mvp/test_local_storage_parquet_adapter.py",
                "tests/hackaithon_mvp/test_data_readiness_audit.py",
            ),
            demo_command="python -m src.hackaithon_mvp.local_storage.storage_cli --capability",
            current_boundary="Local files and static sample evidence only; no Data Gateway.",
            future_work="Future data access layer remains outside this MVP.",
            claim_boundary="No live data or provider calls.",
        ),
        _row(
            diagram_block="quant_core",
            diagram_label="Quant Core",
            mvp_status="implemented",
            implementation_level="static_diagnostic_runtime",
            implemented_modules=(
                "src/hackaithon_mvp/forecast_diagnostic_engine.py",
                "src/hackaithon_mvp/quant_core_policy_runtime.py",
                "src/hackaithon_mvp/diagnostic_chain/quant_core_engine.py",
            ),
            test_files=(
                "tests/hackaithon_mvp/test_forecast_diagnostic_engine.py",
                "tests/hackaithon_mvp/test_quant_core_policy_runtime.py",
                "tests/hackaithon_mvp/test_quant_core_engine.py",
            ),
            demo_command="python -m src.hackaithon_mvp.dag_forecast_output_verification --format report",
            current_boundary="Bounded diagnostic labels from local/static evidence.",
            future_work="Broader evidence review after MVP scope changes.",
            claim_boundary="No training, inference, or benchmark rerun.",
        ),
        _row(
            diagram_block="scenario_engine",
            diagram_label="Scenario Engine",
            mvp_status="implemented",
            implementation_level="dag_local_mode",
            implemented_modules=("src/hackaithon_mvp/diagnostic_chain/scenario_engine.py",),
            test_files=("tests/hackaithon_mvp/test_scenario_engine.py",),
            demo_command="python -m src.hackaithon_mvp.diagnostic_dag.dag_cli --ticker VCB --horizon-steps 1",
            current_boundary="Local diagnostic scenario classification only.",
            future_work="Future scenario evidence can be added after review.",
            claim_boundary="No operational decision.",
        ),
        _row(
            diagram_block="risk_governance",
            diagram_label="Risk Governance",
            mvp_status="implemented",
            implementation_level="diagnostic_risk_routing",
            implemented_modules=("src/hackaithon_mvp/diagnostic_chain/risk_governance_engine.py",),
            test_files=("tests/hackaithon_mvp/test_risk_governance_engine.py",),
            demo_command="python -m src.hackaithon_mvp.diagram_demo_readiness --format report",
            current_boundary="Diagnostic risk labels and flags only.",
            future_work="Expanded governance checks remain later scope.",
            claim_boundary="Human review required.",
        ),
        _row(
            diagram_block="decision_lane",
            diagram_label="Decision Lane",
            mvp_status="implemented",
            implementation_level="review_routing",
            implemented_modules=("src/hackaithon_mvp/diagnostic_chain/decision_lane_engine.py",),
            test_files=("tests/hackaithon_mvp/test_decision_lane_engine.py",),
            demo_command="python -m src.hackaithon_mvp.diagram_demo_readiness --format report",
            current_boundary="Review lane routing only.",
            future_work="Additional reviewer workflow fields can be added later.",
            claim_boundary="No operational authority.",
        ),
        _row(
            diagram_block="market_context",
            diagram_label="Market Context",
            mvp_status="partial",
            implementation_level="local_diagnostic_metadata",
            implemented_modules=("src/hackaithon_mvp/diagnostic_chain/market_context_engine.py",),
            test_files=("tests/hackaithon_mvp/test_market_context_engine.py",),
            demo_command="python -m src.hackaithon_mvp.diagram_coverage_matrix --format report",
            current_boundary="Static context placeholder only.",
            future_work="Reviewed context records remain future scope.",
            claim_boundary="No live context feed.",
        ),
        _row(
            diagram_block="social_listening",
            diagram_label="Social Listening",
            mvp_status="implemented_as_contract",
            implementation_level="schema_contract_only",
            implemented_modules=("src/hackaithon_mvp/social_listening_contract.py",),
            test_files=("tests/hackaithon_mvp/test_social_listening_contract.py",),
            demo_command="python -m src.hackaithon_mvp.social_listening_contract",
            current_boundary="Schema and empty context only; no ingestion.",
            future_work="Future reviewed context evidence can map into the schema.",
            claim_boundary="No API calls, scraping, live data, or sentiment model.",
        ),
        _row(
            diagram_block="fine_tune_engine",
            diagram_label="Fine-Tune Engine",
            mvp_status="future",
            implementation_level="boundary_documented",
            implemented_modules=("src/hackaithon_mvp/public_architecture_alignment.py",),
            test_files=("tests/hackaithon_mvp/test_public_architecture_alignment.py",),
            demo_command="python -m src.hackaithon_mvp.public_architecture_alignment --format report",
            current_boundary="Contract boundary only; no model update process.",
            future_work="Any later model update work requires a separate reviewed scope.",
            claim_boundary="No training or inference.",
        ),
        _row(
            diagram_block="portfolio_allocator",
            diagram_label="Research Allocation View",
            mvp_status="implemented",
            implementation_level="research_sizing_view_only",
            implemented_modules=("src/hackaithon_mvp/diagnostic_chain/portfolio_diagnostic_allocator.py",),
            test_files=("tests/hackaithon_mvp/test_portfolio_diagnostic_allocator.py",),
            demo_command="python -m src.hackaithon_mvp.diagram_demo_readiness --format report",
            current_boundary="Hypothetical research sizing view only.",
            future_work="Reviewer-facing explanation fields can be expanded later.",
            claim_boundary="Not guidance.",
        ),
        _row(
            diagram_block="phase_router",
            diagram_label="Phase Router",
            mvp_status="implemented",
            implementation_level="diagnostic_router",
            implemented_modules=("src/hackaithon_mvp/diagnostic_chain/phase_router.py",),
            test_files=("tests/hackaithon_mvp/test_phase_router.py",),
            demo_command="python -m src.hackaithon_mvp.diagram_demo_readiness --format report",
            current_boundary="Diagnostic route selection only.",
            future_work="Additional review phases remain later scope.",
            claim_boundary="No decision system.",
        ),
        _row(
            diagram_block="feedback_loop",
            diagram_label="Feedback Loop",
            mvp_status="implemented_as_contract",
            implementation_level="human_review_candidate_contract",
            implemented_modules=("src/hackaithon_mvp/feedback_loop_contract.py",),
            test_files=("tests/hackaithon_mvp/test_feedback_loop_contract.py",),
            demo_command="python -m src.hackaithon_mvp.feedback_loop_contract",
            current_boundary="Evaluation metrics can create review candidates only.",
            future_work="Any accepted policy change remains manual and later scope.",
            claim_boundary="No automatic policy update, training, or inference.",
        ),
        _row(
            diagram_block="periodic_output",
            diagram_label="Periodic Output",
            mvp_status="implemented_as_contract",
            implementation_level="local_dry_run_runner_contract",
            implemented_modules=("src/hackaithon_mvp/periodic_diagnostic_runner.py",),
            test_files=("tests/hackaithon_mvp/test_periodic_diagnostic_runner.py",),
            demo_command="python -m src.hackaithon_mvp.periodic_diagnostic_runner --plan",
            current_boundary="Local dry-run runner; no daemon and no default writes.",
            future_work="External scheduling remains outside this MVP.",
            claim_boundary="No background process.",
        ),
        _row(
            diagram_block="dashboard_destination",
            diagram_label="Dashboard Destination",
            mvp_status="implemented_as_local_demo",
            implementation_level="dashboard_artifact_export",
            implemented_modules=("src/hackaithon_mvp/dashboard_artifact_export.py",),
            test_files=("tests/hackaithon_mvp/test_dashboard_artifact_export.py",),
            demo_command="python -m src.hackaithon_mvp.dashboard_artifact_export --format json",
            current_boundary="Compact JSON artifact only; no web dashboard.",
            future_work="Future display layer remains outside this MVP.",
            claim_boundary="No web app built.",
        ),
    )


def summarize_diagram_coverage(matrix: tuple[dict, ...]) -> dict:
    """Summarize status coverage for the diagram matrix."""

    blocks = {str(row.get("diagram_block")) for row in matrix}
    counts = Counter(str(row.get("mvp_status")) for row in matrix)
    return {
        "coverage_status": "complete" if blocks == set(DIAGRAM_BLOCKS) else "incomplete",
        "block_count": len(matrix),
        "required_block_count": len(DIAGRAM_BLOCKS),
        "missing_blocks": sorted(set(DIAGRAM_BLOCKS) - blocks),
        "extra_blocks": sorted(blocks - set(DIAGRAM_BLOCKS)),
        "status_counts": dict(sorted(counts.items())),
        "implemented_like_count": sum(
            counts[status] for status in ("implemented", "implemented_as_contract", "implemented_as_local_demo")
        ),
        "partial_count": counts["partial"],
        "future_count": counts["future"],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_diagram_coverage_report(matrix: tuple[dict, ...]) -> str:
    """Render a compact public-safe diagram coverage report."""

    summary = summarize_diagram_coverage(matrix)
    lines = [
        "# Diagram-to-Code Coverage Matrix",
        "",
        f"Coverage status: {summary['coverage_status']}",
        f"Diagram blocks: {summary['block_count']} of {summary['required_block_count']}",
        f"Status counts: {json.dumps(summary['status_counts'], sort_keys=True)}",
        "",
        "block | status | implementation_level | current_boundary",
        "--- | --- | --- | ---",
    ]
    for row in matrix:
        lines.append(
            " | ".join(
                str(value)
                for value in (
                    row.get("diagram_block"),
                    row.get("mvp_status"),
                    row.get("implementation_level"),
                    row.get("current_boundary"),
                )
            )
        )
    lines.extend(
        [
            "",
            "Boundary: coverage mapping only; no files are written.",
            "Human review remains required.",
            NON_CLAIM_TEXT,
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect architecture diagram coverage.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    matrix = build_diagram_coverage_matrix()
    if args.format == "report":
        print(render_diagram_coverage_report(matrix), end="")
    else:
        print(json.dumps({"matrix": matrix, "summary": summarize_diagram_coverage(matrix)}, indent=2, sort_keys=True))
    return 0 if summarize_diagram_coverage(matrix)["coverage_status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
