"""Public-safe architecture alignment summary for the local MVP."""

from __future__ import annotations

import argparse
import json
from typing import Any


NON_CLAIM_TEXT = "Architecture alignment summary for local research diagnostics; human review remains required."
CLAIM_BOUNDARY = {
    "local_static_research_mvp": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_server_database": True,
    "no_dashboard_web_app": True,
    "human_review_required": True,
}
EXPLICITLY_EXCLUDED = (
    "live_data",
    "provider_api_calls",
    "model_training",
    "model_inference",
    "benchmark_rerun",
    "server_database",
    "dashboard_web_app",
    "Data Gateway",
    "operational_decisions",
)
REQUIRED_CATEGORIES = (
    "implemented_now",
    "local_demo_only",
    "contract_only",
    "future_scope",
    "explicitly_excluded",
)


def build_public_architecture_alignment() -> dict:
    """Build a public-safe summary of implemented, contract, and future scope."""

    return {
        "alignment_status": "aligned_for_local_diagram_demo",
        "implemented_now": [
            "Diagnostic DAG Runtime",
            "Forecast Diagnostic Engine",
            "8-layer diagnostic chain",
            "Policy runtime",
            "Evidence packet and diagnostic report",
            "Local storage adapter",
            "Actual outcome builder",
            "Forecast-actual evaluation",
        ],
        "local_demo_only": [
            "End-to-end local demo",
            "DAG forecast output verification",
            "Periodic diagnostic runner dry-run",
            "Dashboard artifact export",
        ],
        "contract_only": [
            "Data readiness contract",
            "Hybrid storage architecture contract",
            "Social listening schema contract",
            "Feedback loop review-candidate contract",
            "Fine-tune boundary contract",
        ],
        "future_scope": [
            "Data Gateway",
            "server database",
            "dashboard web app",
            "reviewed context ingestion",
            "externally scheduled execution",
        ],
        "explicitly_excluded": list(EXPLICITLY_EXCLUDED),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def audit_architecture_alignment_claims(summary: dict) -> dict:
    """Audit the architecture summary for required categories and boundary flags."""

    errors: list[str] = []
    warnings: list[str] = []
    for category in REQUIRED_CATEGORIES:
        if category not in summary:
            errors.append(f"missing category: {category}")
        elif not summary.get(category):
            warnings.append(f"empty category: {category}")

    excluded = set(summary.get("explicitly_excluded", []) or [])
    missing_exclusions = [item for item in EXPLICITLY_EXCLUDED if item not in excluded]
    errors.extend(f"missing explicit exclusion: {item}" for item in missing_exclusions)

    boundary = summary.get("claim_boundary", {})
    for key, expected in CLAIM_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"claim_boundary.{key} must be {expected}")

    return {
        "is_safe": not errors,
        "errors": errors,
        "warnings": warnings,
        "category_count": len([category for category in REQUIRED_CATEGORIES if category in summary]),
        "explicit_exclusion_count": len(excluded),
        "non_claim": summary.get("non_claim", NON_CLAIM_TEXT),
    }


def render_public_architecture_alignment_report(summary: dict) -> str:
    """Render a compact architecture alignment report."""

    audit = audit_architecture_alignment_claims(summary)
    lines = [
        "# Public Architecture Alignment",
        "",
        f"Alignment status: {summary.get('alignment_status')}",
        f"Audit safe: {audit.get('is_safe')}",
        "",
        "## Categories",
        f"Implemented now: {len(summary.get('implemented_now', []) or [])}",
        f"Local demo only: {len(summary.get('local_demo_only', []) or [])}",
        f"Contract only: {len(summary.get('contract_only', []) or [])}",
        f"Future scope: {len(summary.get('future_scope', []) or [])}",
        f"Explicitly excluded: {len(summary.get('explicitly_excluded', []) or [])}",
        "",
        "## Explicit Exclusions",
        *[f"- {item}" for item in summary.get("explicitly_excluded", [])],
        "",
        "## Boundary",
        "Local/static research MVP only.",
        "No operational decisions are produced.",
        "Human review remains required.",
        str(summary.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect public architecture alignment.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = build_public_architecture_alignment()
    if args.format == "report":
        print(render_public_architecture_alignment_report(summary), end="")
    else:
        print(json.dumps({"summary": summary, "audit": audit_architecture_alignment_claims(summary)}, indent=2, sort_keys=True))
    return 0 if audit_architecture_alignment_claims(summary).get("is_safe") else 1


if __name__ == "__main__":
    raise SystemExit(main())
