"""Pitch-safe claim card for the bounded classical 61 percent VN30 lane."""

from __future__ import annotations

import argparse
import json

from src.hackaithon_mvp.classical_61pct_benchmark_registry import (
    CLAIM_BOUNDARY,
    NON_CLAIM_TEXT,
    load_classical_61pct_evidence,
    validate_classical_61pct_scope,
)


CLAIM_TITLE = "VN30 hourly absolute-direction classical champion reached 61.61% final accuracy over 4,074 rows."
ALLOWED_WORDING = (
    "Within a bounded VN30 hourly absolute-direction benchmark, the classical L2 Logistic champion "
    "reached 61.61% final accuracy over 4,074 rows."
)
NON_CLAIMS = (
    "not broad whole-MVP accuracy",
    "not production readiness",
    "not trading performance",
    "not profitability evidence",
    "not BUY/SELL/HOLD",
    "not the current local fallback gate",
    "not a QML result",
)


def build_classical_61pct_claim_card(*, repo_root: str = ".") -> dict:
    """Build a source-backed exact-scope claim card."""

    evidence = load_classical_61pct_evidence(repo_root=repo_root)
    validation = validate_classical_61pct_scope(evidence)
    claim_allowed = bool(validation.get("claim_allowed_exact_scope"))
    return {
        "claim_card_status": "classical_61pct_claim_card_ready" if claim_allowed else "classical_61pct_claim_card_blocked",
        "claim_title": CLAIM_TITLE,
        "allowed_wording": ALLOWED_WORDING if claim_allowed else None,
        "exact_scope": {
            "universe": evidence.get("universe"),
            "target": evidence.get("target"),
            "model": evidence.get("model"),
            "feature_set": evidence.get("feature_set"),
            "horizon": evidence.get("horizon"),
        },
        "model": evidence.get("model"),
        "target": evidence.get("target"),
        "horizon": evidence.get("horizon"),
        "rows": evidence.get("rows"),
        "final_accuracy": evidence.get("final_accuracy"),
        "final_accuracy_percent": evidence.get("final_accuracy_percent"),
        "final_accuracy_exact": evidence.get("final_accuracy_exact"),
        "lift": evidence.get("lift"),
        "lift_pp": evidence.get("lift_pp"),
        "evidence_path": evidence.get("evidence_path"),
        "claim_allowed": claim_allowed,
        "claim_allowed_only_within_exact_scope": claim_allowed,
        "broad_claim_allowed": False,
        "non_claims": list(NON_CLAIMS),
        "source_evidence_found": evidence.get("source_evidence_found"),
        "validation": validation,
        "registry": evidence,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_classical_61pct_claim_card(result: dict) -> str:
    """Render the bounded classical claim card."""

    scope = result.get("exact_scope") or {}
    lines = [
        "# Classical 61.61% Claim Card",
        "",
        f"Claim card status: {result.get('claim_card_status')}",
        f"Claim title: {result.get('claim_title')}",
        f"Claim allowed: {result.get('claim_allowed')}",
        f"Claim allowed only within exact scope: {result.get('claim_allowed_only_within_exact_scope')}",
        f"Broad claim allowed: {result.get('broad_claim_allowed')}",
        "",
        "Scope:",
        f"- universe: {scope.get('universe')}",
        f"- target: {scope.get('target')}",
        f"- model: {scope.get('model')}",
        f"- feature set: {scope.get('feature_set')}",
        f"- horizon: {scope.get('horizon')}",
        "",
        "Evidence:",
        f"- rows: {result.get('rows')}",
        f"- final accuracy: {result.get('final_accuracy_percent')}%",
        f"- audit exact accuracy: {result.get('final_accuracy_exact')}",
        f"- lift: +{result.get('lift_pp')} pp",
        f"- evidence path: {result.get('evidence_path')}",
        "",
        "Allowed wording:",
        str(result.get("allowed_wording") or "blocked until source evidence validates"),
        "",
        "Non-claims:",
    ]
    lines.extend([f"- {item}" for item in result.get("non_claims") or []])
    lines.extend(["", "Boundary:", str(result.get("non_claim", NON_CLAIM_TEXT))])
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the bounded classical 61 percent claim card.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_classical_61pct_claim_card(repo_root=args.repo_root)
    if args.format == "report":
        print(render_classical_61pct_claim_card(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("claim_allowed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
