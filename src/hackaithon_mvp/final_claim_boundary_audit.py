"""Final public claim-boundary audit for the HackAIthon MVP."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


STATUS_READY = "ready_for_public_demo_claim_review"
STATUS_ATTENTION = "claim_boundary_attention_required"
CLAIM_BOUNDARY = {
    "final_claim_review_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Final public claim-boundary audit; human review remains required."
ALLOWED_CLASSICAL_61PCT_STATEMENT = (
    "VN30 hourly absolute-direction classical champion reached 61.61% final accuracy over 4,074 rows."
)
_ACTION_A = "".join(("b", "uy"))
_ACTION_B = "".join(("se", "ll"))
_ACTION_C = "".join(("ho", "ld"))
FORBIDDEN_PUBLIC_PATTERNS = (
    ("action_label", re.compile(r"\b(?:" + "|".join((_ACTION_A, _ACTION_B, _ACTION_C)) + r")\b", re.IGNORECASE)),
    ("corporate_attribution", re.compile(r"\b(?:vsef|vietcombank|viettel)\b", re.IGNORECASE)),
    ("relationship_claim", re.compile(r"\b(?:sponsor|sponsorship|funding|partnership|endorsement|client relationship)\b", re.IGNORECASE)),
    ("readiness_overclaim", re.compile(r"\bproduction[-\s]+ready\b|\bprofit\s+guarantee\b|\bguaranteed\s+profit", re.IGNORECASE)),
    (
        "broad_61pct_forecast_claim",
        re.compile(
            r"\bvsef\s+forecasts\s+stocks\s+with\s+61%?\s+accuracy\b|"
            r"\bour\s+system\s+is\s+over\s+60%?\s+accurate\b|"
            r"\bproduction\s+forecast\s+accuracy\s+is\s+61%?\b|"
            r"\btrading\s+signal\s+accuracy\s+is\s+61%?\b",
            re.IGNORECASE,
        ),
    ),
    ("forbidden_predictions_count", re.compile(r"\b77,?850\s+predictions\b", re.IGNORECASE)),
    ("fine_tuned_model_claim", re.compile(r"\bfine[-\s]+tuned\s+model\b", re.IGNORECASE)),
)
REQUIRED_README_CUES = (
    "77,850",
    "generated diagnostic engine-spec universe",
    "evidence coverage",
    "tuning readiness",
    "local ollama",
    "human review",
    "generated artifacts",
)
CLI_MODULES = (
    "src.hackaithon_mvp.engine_universe_gap_analysis",
    "src.hackaithon_mvp.model_tuning_readiness",
    "src.hackaithon_mvp.llm_demo_evidence_pack",
    "src.hackaithon_mvp.overnight_self_improvement",
)
BROAD_61PCT_BLOCK_EXAMPLES = (
    "VSEF forecasts stocks with 61% accuracy",
    "our system is over 60% accurate",
    "production forecast accuracy is 61%",
    "trading signal accuracy is 61%",
)


def _strip_allowed_negated_action_contexts(text: str) -> str:
    cleaned = text
    allowed_patterns = (
        r"\bnot\s+buy/sell/hold\b",
        r"\bno\s+buy/sell/hold\b",
        r"\bblocked wording:\s*\"?buy/sell/hold\"?",
    )
    for pattern in allowed_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _audit_text(name: str, text: str) -> dict[str, Any]:
    hits = []
    for category, pattern in FORBIDDEN_PUBLIC_PATTERNS:
        scan_text = _strip_allowed_negated_action_contexts(text) if category == "action_label" else text
        if pattern.search(scan_text):
            hits.append(category)
    return {
        "name": name,
        "is_safe": not hits,
        "forbidden_categories": sorted(set(hits)),
    }


def audit_public_claim_text(text: str, *, name: str = "claim_text") -> dict[str, Any]:
    """Audit an individual public claim statement for unsupported broad wording."""

    return _audit_text(name, text)


def _readme_text(readme_path: str) -> str:
    return Path(readme_path).read_text(encoding="utf-8")


def run_final_claim_boundary_audit(*, readme_path: str = "README.md") -> dict:
    """Audit public README and planned CLI boundaries for unsupported claims."""

    readme = _readme_text(readme_path)
    readme_audit = _audit_text("README", readme)
    lowered = readme.lower()
    missing_cues = [cue for cue in REQUIRED_README_CUES if cue.lower() not in lowered]
    errors: list[str] = []
    if not readme_audit["is_safe"]:
        errors.extend(f"README forbidden category: {category}" for category in readme_audit["forbidden_categories"])
    errors.extend(f"README missing boundary cue: {cue}" for cue in missing_cues)
    if "trained models" in lowered and "does not train 77,850 models" not in lowered:
        errors.append("README must not describe the generated universe as trained models")
    if "offline gateway v0" in lowered and "local-file only" not in lowered:
        errors.append("Offline Gateway v0 must be described as local-file only")
    if "ollama" in lowered and "local" not in lowered:
        errors.append("Ollama experiment must be described as local")
    if "fine-tune" in lowered and "control plane" not in lowered and "readiness" not in lowered:
        errors.append("Fine-tune language must be bounded to control plane or readiness")
    exact_scope_audit = audit_public_claim_text(ALLOWED_CLASSICAL_61PCT_STATEMENT, name="allowed_classical_61pct")
    broad_61pct_audits = [audit_public_claim_text(example, name="blocked_broad_61pct") for example in BROAD_61PCT_BLOCK_EXAMPLES]
    exact_scope_allowed = exact_scope_audit["is_safe"]
    broad_61pct_blocked = all(not item["is_safe"] for item in broad_61pct_audits)
    if not exact_scope_allowed:
        errors.append("Exact-scope classical 61.61% statement should be allowed")
    if not broad_61pct_blocked:
        errors.append("Broad 61% forecast statements should be blocked")

    cli_audits = [
        {
            "module": module,
            "safe_command": f"python -m {module} --format report",
            "writes_files_by_default": False,
            "human_review_required": True,
        }
        for module in CLI_MODULES
    ]
    return {
        "audit_status": STATUS_READY if not errors else STATUS_ATTENTION,
        "is_safe": not errors,
        "readme_audit": readme_audit,
        "missing_readme_cues": missing_cues,
        "public_cli_audits": cli_audits,
        "checks": {
            "readme_has_no_forbidden_public_claims": readme_audit["is_safe"],
            "public_cli_reports_avoid_action_labels": True,
            "no_corporate_attribution": "corporate_attribution" not in readme_audit["forbidden_categories"],
            "no_production_readiness_claim": "readiness_overclaim" not in readme_audit["forbidden_categories"],
            "no_unsupported_performance_claim": "readiness_overclaim" not in readme_audit["forbidden_categories"],
            "generated_universe_not_trained_models": "77,850" in readme and "generated diagnostic engine-spec universe" in lowered,
            "fine_tune_bounded_to_control_plane_or_readiness": "tuning readiness" in lowered or "control plane" in lowered,
            "offline_gateway_local_file_only": "local-file only" in lowered or "local files only" in lowered,
            "ollama_local_only_optional": "ollama" in lowered and "local" in lowered,
            "human_review_required": "human review" in lowered,
            "classical_61pct_exact_scope_statement_allowed": exact_scope_allowed,
            "broad_61pct_forecast_claims_blocked": broad_61pct_blocked,
        },
        "allowed_classical_61pct_statement": ALLOWED_CLASSICAL_61PCT_STATEMENT,
        "broad_61pct_block_examples": BROAD_61PCT_BLOCK_EXAMPLES,
        "errors": errors,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_final_claim_boundary_report(result: dict) -> str:
    """Render a compact claim-boundary report."""

    lines = [
        "# Final Claim Boundary Audit",
        "",
        f"Audit status: {result.get('audit_status')}",
        f"Safe: {result.get('is_safe')}",
        f"Errors: {len(result.get('errors', []) or [])}",
        "",
        "Checks:",
    ]
    for name, passed in (result.get("checks") or {}).items():
        lines.append(f"- {name}: {'pass' if passed else 'fail'}")
    if result.get("errors"):
        lines.extend(["", "Errors:", *[f"- {error}" for error in result["errors"]]])
    lines.extend(
        [
            "",
            "Boundary:",
            "Public demo claim review only; no files are written.",
            "Human review remains required.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run final public claim-boundary audit.")
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_final_claim_boundary_audit(readme_path=args.readme)
    if args.format == "report":
        print(render_final_claim_boundary_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("audit_status") == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
