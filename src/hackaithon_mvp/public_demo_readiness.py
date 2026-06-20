"""Local public demo readiness checks for the HackAIthon MVP."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


CLAIM_BOUNDARY = {
    "local_readiness_check_only": True,
    "writes_files": False,
    "data_gateway_created": False,
    "server_database_created": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_enabled": False,
    "inference_enabled": False,
    "benchmark_rerun": False,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local readiness audit only; public demo use still requires human review."
SUBMISSION_RECOMMENDATION = "safe_for_local_public_demo_after_human_review"
REQUIRED_README_PHRASES = (
    "research-only",
    "diagnostic-only",
    "baseline ml-only",
    "human-review required",
    "no data gateway",
    "no live data",
    "no provider api calls",
    "no model training",
    "no model inference",
    "no benchmark rerun",
    "no action-oriented output",
    "no production readiness claim",
    "no profitability guarantee",
    "python -m src.hackaithon_mvp.end_to_end_demo",
    "python -m pytest tests/hackaithon_mvp -q --basetemp .pytest-tmp",
    "passed",
)
STALE_README_MARKERS = (
    "# VSEF HackAIthon 2026 MVP",
    "Forecast Diagnostic Engine | Next",
    "8-Layer Diagnostic Chain | Next",
    "Push is currently blocked",
)
FORBIDDEN_GROUPS = {
    "corporate_attribution": (
        "v" + "sef",
        "viet" + "combank",
        "viet" + "tel",
    ),
    "relationship_claim": (
        "sponsor",
        "sponsorship",
        "partner",
        "partnership",
        "funding",
        "endorsement",
        "deployment approval",
        "client relationship",
    ),
    "excluded_scope_label": (
        "q" + "ml",
        "non-" + "qml",
        "non" + "qml",
    ),
    "market_action": (
        "buy",
        "sell",
        "hold",
        "trading signal",
        "trade recommendation",
        "market action",
    ),
    "advice_claim": (
        "financial advice",
        "investment advice",
        "portfolio allocation advice",
    ),
    "readiness_overclaim": (
        "production-ready",
        "production ready",
        "profit guarantee",
        "guaranteed profit",
        "guaranteed profitability",
    ),
}


def _word_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.lower()).replace("\\ ", r"\s+")
    if re.fullmatch(r"[a-z0-9]+", term.lower()):
        return re.compile(rf"\b{escaped}\b")
    return re.compile(escaped)


def _forbidden_hits(text: str) -> tuple[dict[str, Any], ...]:
    lowered = text.lower()
    hits: list[dict[str, Any]] = []
    for category, terms in FORBIDDEN_GROUPS.items():
        matches = []
        for term in terms:
            if _word_pattern(term).search(lowered):
                matches.append(term)
        if matches:
            hits.append({"category": category, "count": len(matches)})
    return tuple(hits)


def _command(command: str, purpose: str) -> dict[str, Any]:
    return {
        "command": command,
        "purpose": purpose,
        "writes_files": False,
        "requires_storage_root": False,
        "requires_live_data": False,
        "requires_provider": False,
        "runs_training": False,
        "runs_inference": False,
        "runs_benchmark": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }


def get_public_demo_commands() -> tuple[dict, ...]:
    """Return the local-only public demo command registry."""

    return (
        _command(
            "python -m src.hackaithon_mvp.end_to_end_demo",
            "Run the deterministic local end-to-end demo summary.",
        ),
        _command(
            "python -m src.hackaithon_mvp.end_to_end_demo --format report",
            "Render the deterministic local demo as a compact report.",
        ),
        _command(
            'python -m src.hackaithon_mvp.diagnostic_dag.dag_cli --ticker DEMO --timeframe "1 ngày" --horizon-steps 1',
            "Run the static diagnostic DAG with a synthetic ticker context.",
        ),
        _command(
            "python -m src.hackaithon_mvp.local_storage.storage_cli --capability",
            "Inspect local storage capability without writing files.",
        ),
        _command(
            "python -m src.hackaithon_mvp.hybrid_storage_architecture --section architecture",
            "Inspect the local hybrid storage architecture contract.",
        ),
        _command(
            "python -m src.hackaithon_mvp.data_readiness_audit --cases-per-pair 10000",
            "Inspect the storage-readiness contract without external data access.",
        ),
    )


def audit_public_claim_boundaries(text: str) -> dict:
    """Audit a public-facing text block for claim-boundary safety."""

    hits = _forbidden_hits(text)
    errors = [f"forbidden public wording category found: {hit['category']}" for hit in hits]
    warnings: list[str] = []
    lowered = text.lower()
    for expected in ("human review", "local", "diagnostic"):
        if expected not in lowered:
            warnings.append(f"missing boundary cue: {expected}")
    return {
        "is_safe": not errors,
        "errors": errors,
        "warnings": warnings,
        "forbidden_hits": list(hits),
        "non_claim": NON_CLAIM_TEXT,
    }


def audit_public_readme(readme_text: str) -> dict:
    """Audit README text for public demo readiness."""

    lowered = readme_text.lower()
    errors: list[str] = []
    warnings: list[str] = []
    missing = [phrase for phrase in REQUIRED_README_PHRASES if phrase not in lowered]
    if missing:
        errors.extend(f"missing README boundary phrase: {phrase}" for phrase in missing)
    stale = [marker for marker in STALE_README_MARKERS if marker.lower() in lowered]
    if stale:
        errors.extend(f"stale README marker present: {marker}" for marker in stale)
    if not re.search(r"\b\d+\s+passed\b", lowered):
        errors.append("expected pass count is not documented")

    claim_audit = audit_public_claim_boundaries(readme_text)
    errors.extend(claim_audit["errors"])
    warnings.extend(claim_audit["warnings"])
    return {
        "is_safe": not errors,
        "required_phrase_count": len(REQUIRED_README_PHRASES),
        "missing_required_phrases": missing,
        "stale_markers": stale,
        "errors": errors,
        "warnings": warnings,
        "forbidden_hits": claim_audit["forbidden_hits"],
        "non_claim": NON_CLAIM_TEXT,
    }


def _manual_items(include_git_status: bool) -> list[str]:
    items = [
        "remaining untracked configs/ require user decision before any submission tag",
        "remaining untracked scripts/ require user decision before any submission tag",
        "dashboard/API remains later scope",
        "Data Gateway remains excluded",
        "server database remains excluded",
    ]
    if include_git_status:
        try:
            completed = subprocess.run(
                ["git", "status", "--short"],
                check=True,
                capture_output=True,
                text=True,
            )
            visible = [line for line in completed.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.CalledProcessError):
            visible = []
        if visible:
            items.append(f"visible local status entries: {len(visible)}")
    return items


def build_public_demo_readiness_summary(
    *,
    readme_path: str = "README.md",
    include_git_status: bool = False,
) -> dict:
    """Build a deterministic local public demo readiness summary."""

    path = Path(readme_path)
    readme_text = path.read_text(encoding="utf-8")
    readme_audit = audit_public_readme(readme_text)
    claim_audit = audit_public_claim_boundaries(readme_text)
    commands = get_public_demo_commands()
    default_commands_write_files = any(command["writes_files"] for command in commands)
    requires_live_data = any(command["requires_live_data"] for command in commands)
    requires_provider = any(command["requires_provider"] for command in commands)
    runs_training = any(command["runs_training"] for command in commands)
    runs_inference = any(command["runs_inference"] for command in commands)
    runs_benchmark = any(command["runs_benchmark"] for command in commands)
    is_ready = readme_audit["is_safe"] and claim_audit["is_safe"]
    return {
        "readiness_status": "ready_with_manual_review" if is_ready else "not_ready",
        "readme_audit": readme_audit,
        "claim_boundary_audit": claim_audit,
        "demo_commands": commands,
        "demo_command_count": len(commands),
        "default_commands_write_files": default_commands_write_files,
        "requires_live_data": requires_live_data,
        "requires_provider": requires_provider,
        "runs_training": runs_training,
        "runs_inference": runs_inference,
        "runs_benchmark": runs_benchmark,
        "submission_recommendation": SUBMISSION_RECOMMENDATION if is_ready else "human_review_required_before_demo",
        "remaining_manual_items": _manual_items(include_git_status),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_public_demo_readiness_report(summary: dict) -> str:
    """Render a compact neutral readiness report."""

    lines = [
        "# Public Demo Readiness",
        "",
        "## Status",
        f"Readiness status: {summary.get('readiness_status')}",
        f"Submission recommendation: {summary.get('submission_recommendation')}",
        "",
        "## Command Registry",
        f"Demo command count: {summary.get('demo_command_count')}",
        f"Default commands write files: {summary.get('default_commands_write_files')}",
        f"Requires live data: {summary.get('requires_live_data')}",
        f"Requires provider: {summary.get('requires_provider')}",
        f"Runs training: {summary.get('runs_training')}",
        f"Runs inference: {summary.get('runs_inference')}",
        f"Runs benchmark: {summary.get('runs_benchmark')}",
        "",
        "## README Audit",
        f"README safe: {summary.get('readme_audit', {}).get('is_safe')}",
        f"README errors: {len(summary.get('readme_audit', {}).get('errors', []) or [])}",
        "",
        "## Claim Boundary Audit",
        f"Claim boundary safe: {summary.get('claim_boundary_audit', {}).get('is_safe')}",
        f"Forbidden hit categories: {len(summary.get('claim_boundary_audit', {}).get('forbidden_hits', []) or [])}",
        "",
        "## Manual Items",
        *[f"- {item}" for item in summary.get("remaining_manual_items", [])],
        "",
        "## Boundary",
        "Local-only readiness check. No file writes are performed.",
        "Human review remains required.",
        str(summary.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local public demo readiness check.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--readme", default="README.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        summary = build_public_demo_readiness_summary(readme_path=args.readme)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    if args.format == "report":
        print(render_public_demo_readiness_report(summary), end="")
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary.get("readiness_status") == "ready_with_manual_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
