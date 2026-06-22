"""Gap analysis for the generated engine-spec universe."""

from __future__ import annotations

import argparse
import json
from typing import Any


TOTAL_DISCOVERED = 77_850
TOTAL_ATTEMPTED = 77_850
COMPLETED_COUNT = 120
SKIPPED_COUNT = 77_730
FAILED_COUNT = 0
COVERAGE_RATIO = 0.001541
INSUFFICIENT_EVIDENCE_COUNT = 77_730
EXPLORATORY_ONLY_COUNT = 60
NEUTRAL_OR_UNCERTAIN_COUNT = 60
SKIP_REASON_DISTRIBUTION = {
    "required dependency outputs unavailable": 45_000,
    "no matching static evidence for model target horizon": 32_730,
}
FAMILY_DISTRIBUTION = {
    "ensemble_regime": 27_600,
    "classification": 19_050,
    "baseline": 10_950,
    "statistical": 7_500,
    "deep_learning": 6_900,
    "regression": 5_850,
}
HORIZON_DISTRIBUTION = {"1": 15_570, "5": 15_570, "10": 15_570, "20": 15_570, "40": 15_570}
CLAIM_BOUNDARY = {
    "generated_spec_universe": True,
    "active_prediction_count": False,
    "trained_model_count": False,
    "local_static_evidence_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "writes_files_by_default": False,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Generated diagnostic spec coverage analysis; stronger claims require more local evidence."
PRIORITIES = (
    "add local evidence packs for highest-frequency family and horizon gaps",
    "provide forecast_rows for common baseline specs",
    "provide dependency outputs for auxiliary and stack specs",
    "increase local actual bar coverage",
    "avoid describing the generated universe as active predictions until coverage improves",
)


def _gap_ratio(count: int) -> float:
    return round(count / TOTAL_ATTEMPTED, 6) if TOTAL_ATTEMPTED else 0.0


def run_engine_universe_gap_analysis() -> dict:
    """Return a deterministic explanation of latest generated-universe coverage gaps."""

    family_gaps = {
        family: {
            "spec_count": count,
            "share_of_universe": _gap_ratio(count),
            "gap_status": "requires_more_local_evidence_or_dependencies",
        }
        for family, count in FAMILY_DISTRIBUTION.items()
    }
    horizon_gaps = {
        horizon: {
            "spec_count": count,
            "share_of_universe": _gap_ratio(count),
            "gap_status": "requires_matching_local_rows",
        }
        for horizon, count in HORIZON_DISTRIBUTION.items()
    }
    return {
        "gap_status": "needs_evidence_before_stronger_claims",
        "total_specs_discovered": TOTAL_DISCOVERED,
        "total_specs_attempted": TOTAL_ATTEMPTED,
        "completed_count": COMPLETED_COUNT,
        "skipped_count": SKIPPED_COUNT,
        "failed_count": FAILED_COUNT,
        "evidence_coverage_ratio": COVERAGE_RATIO,
        "diagnostic_distribution": {
            "insufficient_evidence": INSUFFICIENT_EVIDENCE_COUNT,
            "exploratory_only": EXPLORATORY_ONLY_COUNT,
            "neutral_or_uncertain": NEUTRAL_OR_UNCERTAIN_COUNT,
        },
        "skip_reason_distribution": dict(SKIP_REASON_DISTRIBUTION),
        "family_distribution": dict(FAMILY_DISTRIBUTION),
        "horizon_distribution": dict(HORIZON_DISTRIBUTION),
        "family_level_gap": family_gaps,
        "horizon_level_gap": horizon_gaps,
        "dependency_output_gap": {
            "affected_specs": SKIP_REASON_DISTRIBUTION["required dependency outputs unavailable"],
            "share_of_universe": _gap_ratio(SKIP_REASON_DISTRIBUTION["required dependency outputs unavailable"]),
            "gap_reason": "auxiliary and stack specs need upstream local diagnostic outputs",
        },
        "missing_static_evidence_gap": {
            "affected_specs": SKIP_REASON_DISTRIBUTION["no matching static evidence for model target horizon"],
            "share_of_universe": _gap_ratio(SKIP_REASON_DISTRIBUTION["no matching static evidence for model target horizon"]),
            "gap_reason": "baseline-style specs need matching local target and horizon evidence rows",
        },
        "why_only_120_completed": (
            "Only specs with matching static evidence and no missing dependency outputs completed; the rest skipped "
            "safely instead of fabricating results."
        ),
        "coverage_priorities": list(PRIORITIES),
        "blocking_claims": [
            "do not describe the generated universe as trained models",
            "do not describe skipped specs as active predictions",
            "do not make stronger evidence claims until local evidence and dependency outputs improve",
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _distribution_lines(distribution: dict[str, Any]) -> list[str]:
    if not distribution:
        return ["- none"]
    return [f"- {key}: {value}" for key, value in distribution.items()]


def render_engine_universe_gap_report(result: dict) -> str:
    """Render a compact public-safe gap report."""

    lines = [
        "# Engine Universe Gap Analysis",
        "",
        f"Gap status: {result.get('gap_status')}",
        f"Total specs discovered: {result.get('total_specs_discovered')}",
        f"Total specs attempted: {result.get('total_specs_attempted')}",
        f"Completed specs: {result.get('completed_count')}",
        f"Skipped specs: {result.get('skipped_count')}",
        f"Failed specs: {result.get('failed_count')}",
        f"Evidence coverage ratio: {result.get('evidence_coverage_ratio')}",
        "",
        "Why only 120 completed:",
        str(result.get("why_only_120_completed")),
        "",
        "Skip reasons:",
        *_distribution_lines(result.get("skip_reason_distribution", {})),
        "",
        "Family distribution:",
        *_distribution_lines(result.get("family_distribution", {})),
        "",
        "Horizon distribution:",
        *_distribution_lines(result.get("horizon_distribution", {})),
        "",
        "Coverage priorities:",
        *[f"- {item}" for item in result.get("coverage_priorities", [])],
        "",
        "Boundary:",
        "77,850 is a generated diagnostic spec universe, not a count of trained models.",
        "Stronger claims require more local evidence and dependency outputs.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explain local evidence gaps in the generated engine-spec universe.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_engine_universe_gap_analysis()
    if args.format == "report":
        print(render_engine_universe_gap_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
