"""Source-backed registry for the bounded classical 61 percent VN30 lane."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PRIMARY_EVIDENCE_PATH = "reports/results/VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md"
FEASIBILITY_EVIDENCE_PATH = "reports/proposal_feasibility_evidence_pack/FEASIBILITY_EVIDENCE_SUMMARY.md"
AUDIT_EVIDENCE_PATH = "reports/generated/vn30_model_universe_benchmark/audit_result.md"
CLAIM_BOUNDARY_PATH = "reports/generated/vn30_model_universe_benchmark/model_universe_claim_boundary.md"
CLAIM_STATUS = "bounded_exact_scope_only"
MISSING_STATUS = "classic_61pct_source_evidence_missing"
VALID_STATUS = "classical_61pct_scope_valid"
INVALID_STATUS = "classical_61pct_scope_invalid"
CLAIM_BOUNDARY = {
    "exact_scope_only": True,
    "not_broad_system_claim": True,
    "not_current_local_fallback_gate": True,
    "not_qml": True,
    "no_training": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = (
    "The classical 61.61% lane is bounded to the archived VN30 hourly absolute-direction "
    "benchmark scope and is not a broad forecasting claim."
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _source_record(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = repo_root / relative_path
    text = _read_text(path)
    return {
        "path": relative_path,
        "exists": path.exists(),
        "contains_61_61": "61.61" in text,
        "contains_61_634": "61.634" in text or "0.6163475699558174" in text,
        "contains_feature_set_c_closest": "feature_set_C_closest" in text,
        "contains_baseline_c_closest": "baseline_C_closest" in text,
        "contains_absolute_direction": "absolute_direction" in text,
        "contains_h40": bool(re.search(r"\bh40\b|\b40\b", text, re.IGNORECASE)),
        "contains_logistic": "Logistic" in text or "logistic" in text,
    }


def _parse_primary_summary(text: str) -> dict[str, Any] | None:
    match = re.search(
        r"Current claimable champion:\s*"
        r"(?P<model>[^,]+),\s*"
        r"(?P<feature_set>[^,]+),\s*"
        r"(?P<horizon>h\d+),\s*"
        r"threshold\s*(?P<threshold>[0-9.]+),\s*"
        r"(?P<accuracy_percent>[0-9.]+)%\s*final accuracy,\s*"
        r"\+(?P<lift_pp>[0-9.]+)\s*pp lift,\s*"
        r"(?P<rows>[0-9,]+)\s*rows",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    groups = match.groupdict()
    accuracy_percent = float(groups["accuracy_percent"])
    lift_pp = float(groups["lift_pp"])
    return {
        "model": groups["model"].strip(),
        "feature_set": groups["feature_set"].strip(),
        "horizon": groups["horizon"].strip(),
        "threshold": groups["threshold"].strip(),
        "final_accuracy": round(accuracy_percent / 100.0, 10),
        "final_accuracy_percent": accuracy_percent,
        "lift_pp": lift_pp,
        "lift": round(lift_pp / 100.0, 10),
        "rows": int(groups["rows"].replace(",", "")),
    }


def _parse_exact_accuracy(texts: list[str]) -> float | None:
    joined = "\n".join(texts)
    exact = re.search(r"0\.6163475699558174", joined)
    if exact:
        return 0.6163475699558174
    percent = re.search(r"61\.6347569956%?", joined)
    if percent:
        return 0.6163475699558174
    return None


def load_classical_61pct_evidence(*, repo_root: str = ".") -> dict:
    """Load the archived bounded classical 61 percent evidence from local reports."""

    root = Path(repo_root)
    source_paths = [
        PRIMARY_EVIDENCE_PATH,
        FEASIBILITY_EVIDENCE_PATH,
        AUDIT_EVIDENCE_PATH,
        CLAIM_BOUNDARY_PATH,
        "reports/claims/VN30_FULL_MODEL_RESURRECTION_AND_INDEX_PRETRAIN_CLAIM_BOUNDARY.md",
        "reports/claims/VN30_V8_STRATEGY_TARGET_REDESIGN_CLAIM_BOUNDARY.md",
    ]
    sources = [_source_record(root, path) for path in source_paths]
    primary_path = root / PRIMARY_EVIDENCE_PATH
    primary_text = _read_text(primary_path)
    parsed = _parse_primary_summary(primary_text)
    if not primary_path.exists() or parsed is None:
        return {
            "registry_status": MISSING_STATUS,
            "source_evidence_found": False,
            "evidence_path": PRIMARY_EVIDENCE_PATH,
            "source_files": sources,
            "missing_reason": "primary_v3_summary_missing_or_champion_line_not_found",
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }

    supporting_texts = [_read_text(root / path) for path in source_paths[1:]]
    exact_accuracy = _parse_exact_accuracy(supporting_texts)
    audit_text = _read_text(root / AUDIT_EVIDENCE_PATH)
    claim_boundary_text = _read_text(root / CLAIM_BOUNDARY_PATH)
    baseline_accuracy = round(parsed["final_accuracy"] - parsed["lift"], 10)
    evidence = {
        "track": "Classical absolute-direction champion",
        "universe": "VN30 hourly",
        "target": "absolute_direction" if "absolute_direction" in primary_text else None,
        "model": parsed["model"],
        "model_id": "logistic_l2",
        "model_family": "classical_logistic_regression",
        "feature_set": parsed["feature_set"],
        "feature_aliases": ["baseline_C_closest"] if "baseline_C_closest" in "\n".join(supporting_texts) else [],
        "horizon": parsed["horizon"],
        "threshold": parsed["threshold"],
        "final_accuracy": parsed["final_accuracy"],
        "final_accuracy_percent": parsed["final_accuracy_percent"],
        "final_accuracy_exact": exact_accuracy,
        "final_accuracy_exact_percent": round(exact_accuracy * 100.0, 10) if exact_accuracy is not None else None,
        "lift": parsed["lift"],
        "lift_pp": parsed["lift_pp"],
        "baseline_accuracy": baseline_accuracy,
        "baseline_accuracy_percent": round(baseline_accuracy * 100.0, 4),
        "rows": parsed["rows"],
        "evidence_path": PRIMARY_EVIDENCE_PATH,
        "supporting_evidence_paths": [
            path for path in (FEASIBILITY_EVIDENCE_PATH, AUDIT_EVIDENCE_PATH, CLAIM_BOUNDARY_PATH) if (root / path).exists()
        ],
        "validation_final_policy": (
            "validation-only selection with final scoring-only evaluation"
            if "validation-selected" in audit_text or "Final-window scores are scoring-only" in claim_boundary_text
            else "not_confirmed"
        ),
        "limitations": [
            "exact-scope benchmark evidence only",
            "not mixed with later local fallback forecast-edge runs",
            "not a broad whole-MVP forecast-performance claim",
            "not QML evidence",
            "human review required",
        ],
        "claim_status": CLAIM_STATUS,
        "source_files": sources,
        "source_assertions": {
            "primary_source_exists": primary_path.exists(),
            "primary_states_61_61": "61.61" in primary_text,
            "supporting_sources_state_61_634": exact_accuracy is not None,
            "primary_states_rows": "4,074 rows" in primary_text or "4074 rows" in primary_text,
            "audit_keeps_h40_main_claim_separate": "h40 main claim kept separate" in audit_text,
            "claim_boundary_blocks_broad_use": "No trading" in claim_boundary_text and "generalization beyond" in claim_boundary_text,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    return {
        "registry_status": "classical_61pct_source_evidence_found",
        "source_evidence_found": True,
        **evidence,
    }


def validate_classical_61pct_scope(evidence: dict) -> dict:
    """Validate that loaded evidence matches the exact bounded 61 percent lane."""

    checks = {
        "source_evidence_found": bool(evidence.get("source_evidence_found")),
        "target_absolute_direction": evidence.get("target") == "absolute_direction",
        "universe_vn30_hourly": evidence.get("universe") == "VN30 hourly",
        "model_l2_logistic": "l2" in str(evidence.get("model") or "").lower()
        and "logistic" in str(evidence.get("model") or "").lower(),
        "feature_set_c_closest": evidence.get("feature_set") == "feature_set_C_closest",
        "horizon_h40": evidence.get("horizon") == "h40",
        "final_accuracy_at_least_61pct": float(evidence.get("final_accuracy_exact") or evidence.get("final_accuracy") or 0.0) >= 0.61,
        "rows_at_least_4000": int(evidence.get("rows") or 0) >= 4000,
        "evidence_path_exists": any(
            item.get("path") == evidence.get("evidence_path") and item.get("exists")
            for item in evidence.get("source_files") or []
        ),
        "bounded_exact_scope_only": evidence.get("claim_status") == CLAIM_STATUS,
        "no_broad_forecast_claim": bool((evidence.get("claim_boundary") or {}).get("not_broad_system_claim")),
        "no_trading_claim": "trading" not in str(evidence.get("claim_status") or "").lower()
        and bool((evidence.get("claim_boundary") or {}).get("exact_scope_only")),
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "validation_status": VALID_STATUS if not errors else INVALID_STATUS,
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "claim_allowed_exact_scope": not errors,
        "broad_claim_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_classical_61pct_benchmark_report(result: dict) -> str:
    """Render a compact report for the bounded classical 61 percent lane."""

    evidence = result
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else validate_classical_61pct_scope(result)
    lines = [
        "# Classical 61.61% Benchmark Registry",
        "",
        f"Registry status: {evidence.get('registry_status')}",
        f"Source evidence found: {evidence.get('source_evidence_found')}",
        f"Evidence path: {evidence.get('evidence_path')}",
        f"Track: {evidence.get('track')}",
        f"Scope: {evidence.get('universe')} / {evidence.get('target')}",
        f"Model: {evidence.get('model')}",
        f"Feature set: {evidence.get('feature_set')}",
        f"Horizon: {evidence.get('horizon')}",
        f"Rows: {evidence.get('rows')}",
        f"Final accuracy: {evidence.get('final_accuracy_percent')}%",
        f"Audit exact accuracy: {evidence.get('final_accuracy_exact')}",
        f"Lift: +{evidence.get('lift_pp')} pp",
        f"Baseline accuracy: {evidence.get('baseline_accuracy_percent')}%",
        f"Validation/final policy: {evidence.get('validation_final_policy')}",
        f"Validation status: {validation.get('validation_status')}",
        f"Exact-scope claim allowed: {validation.get('claim_allowed_exact_scope')}",
        f"Broad claim allowed: {validation.get('broad_claim_allowed')}",
        "",
        "Limitations:",
    ]
    lines.extend([f"- {item}" for item in evidence.get("limitations") or ["source evidence missing"]])
    if validation.get("errors"):
        lines.extend(["", "Validation errors:", *[f"- {error}" for error in validation["errors"]]])
    lines.extend(["", "Boundary:", str(evidence.get("non_claim", NON_CLAIM_TEXT))])
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load the bounded classical 61 percent benchmark evidence lane.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    evidence = load_classical_61pct_evidence(repo_root=args.repo_root)
    validation = validate_classical_61pct_scope(evidence)
    result = {**evidence, "validation": validation}
    if args.format == "report":
        print(render_classical_61pct_benchmark_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if evidence.get("source_evidence_found") else 1


if __name__ == "__main__":
    raise SystemExit(main())
