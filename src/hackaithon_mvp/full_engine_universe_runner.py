"""Run generated engine specs against materialized local evidence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_catalog.stack_catalog_generator import generate_stack_catalog
from src.hackaithon_mvp.engine_catalog.support_catalog_generator import generate_support_catalog
from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine
from src.hackaithon_mvp.static_evidence_loader import load_static_evidence


PREVIOUS_COMPLETED = 120
PREVIOUS_SKIPPED = 77_730
CLAIM_BOUNDARY = {
    "generated_evidence_sweep": True,
    "writes_summary_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_model_update": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Generated-evidence engine sweep; completion counts are diagnostic coverage, not performance claims."


def _read_dependency_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    results: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                key = str(item.get("dependency_id") or item.get("engine_id") or "")
                if key:
                    results[key] = item
    return results


def _all_specs():
    yield from generate_baseline_catalog()
    yield from generate_support_catalog()
    yield from generate_stack_catalog()


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    allowed = (".tmp_full_model_run", ".tmp_performance_rescue", ".tmp_accuracy_maximization", ".tmp_forecast_repair")
    if not any(part.lower().startswith(allowed) for part in root.parts):
        raise ValueError("output_root must be under an explicit local temp model-run root")
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_engine_universe_with_generated_evidence(
    *,
    evidence_root: str,
    output_root: str,
    max_specs: int | None = None,
) -> dict:
    """Run all generated specs that can match local materialized evidence."""

    evidence_path = Path(evidence_root)
    out_root = _output_root(output_root)
    evidence_records = load_static_evidence(evidence_path / "static_evidence.json")
    dependency_results = _read_dependency_results(evidence_path / "dependency_results.jsonl")
    counters = {
        "status": Counter(),
        "family": Counter(),
        "horizon": Counter(),
        "model": Counter(),
        "completed_family": Counter(),
        "completed_horizon": Counter(),
        "completed_model": Counter(),
        "skip": Counter(),
    }
    samples: list[dict[str, Any]] = []
    attempted = 0
    for spec in _all_specs():
        if max_specs is not None and attempted >= max_specs:
            break
        attempted += 1
        try:
            result = run_engine(spec, evidence_records=evidence_records, dependency_results=dependency_results)
            status = result.status
            warnings = list(result.warnings)
        except Exception as exc:  # noqa: BLE001 - isolate per spec.
            status = "failed"
            warnings = [f"{type(exc).__name__}: {exc}"]
        counters["status"][status] += 1
        counters["family"][str(spec.model_family)] += 1
        counters["horizon"][str(spec.horizon)] += 1
        counters["model"][str(spec.model_key or spec.engine_type)] += 1
        if status == "completed":
            counters["completed_family"][str(spec.model_family)] += 1
            counters["completed_horizon"][str(spec.horizon)] += 1
            counters["completed_model"][str(spec.model_key or spec.engine_type)] += 1
        if status != "completed":
            reason = warnings[0] if warnings else status
            counters["skip"][reason] += 1
        if len(samples) < 25 and (status == "completed" or status not in {sample.get("status") for sample in samples}):
            samples.append(
                {
                    "engine_id": spec.engine_id,
                    "engine_type": spec.engine_type,
                    "model_key": spec.model_key,
                    "model_family": spec.model_family,
                    "target": spec.target,
                    "horizon": spec.horizon,
                    "status": status,
                    "skip_reason": None if status == "completed" else (warnings[0] if warnings else status),
                }
            )
    completed = counters["status"].get("completed", 0)
    skipped = attempted - completed - counters["status"].get("failed", 0)
    failed = counters["status"].get("failed", 0)
    summary = {
        "engine_universe_run_status": "completed_with_generated_evidence",
        "evidence_root": str(evidence_path),
        "output_root": str(out_root),
        "total_specs_attempted": attempted,
        "completed_count": completed,
        "skipped_count": skipped,
        "failed_count": failed,
        "completion_ratio": round(completed / attempted, 6) if attempted else 0.0,
        "previous_completed_count": PREVIOUS_COMPLETED,
        "previous_skipped_count": PREVIOUS_SKIPPED,
        "completed_improvement": completed - PREVIOUS_COMPLETED,
        "skipped_reduction": PREVIOUS_SKIPPED - skipped,
        "completed_by_family": dict(sorted(counters["completed_family"].items())),
        "completed_by_horizon": dict(sorted(counters["completed_horizon"].items())),
        "completed_by_model": dict(sorted(counters["completed_model"].items())),
        "attempted_by_family": dict(sorted(counters["family"].items())),
        "attempted_by_horizon": dict(sorted(counters["horizon"].items())),
        "attempted_by_model": dict(sorted(counters["model"].items())),
        "status_distribution": dict(sorted(counters["status"].items())),
        "skip_reason_distribution": dict(counters["skip"].most_common(20)),
        "representative_samples": samples,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    (out_root / "engine_universe_generated_evidence_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return summary


def render_full_engine_universe_run_report(result: dict) -> str:
    """Render compact generated-evidence sweep report."""

    lines = [
        "# Full Engine Universe Run With Generated Evidence",
        "",
        f"Run status: {result.get('engine_universe_run_status')}",
        f"Attempted specs: {result.get('total_specs_attempted')}",
        f"Completed specs: {result.get('completed_count')}",
        f"Skipped specs: {result.get('skipped_count')}",
        f"Failed specs: {result.get('failed_count')}",
        f"Completion ratio: {result.get('completion_ratio')}",
        f"Previous completed specs: {result.get('previous_completed_count')}",
        f"Completed improvement: {result.get('completed_improvement')}",
        f"Skipped reduction: {result.get('skipped_reduction')}",
        "",
        "Top remaining skip reasons:",
    ]
    skips = result.get("skip_reason_distribution") or {}
    lines.extend([f"- {key}: {value}" for key, value in skips.items()] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Completion counts mean generated specs found local evidence or dependency outputs.",
            "No metrics are fabricated for skipped specs.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run generated engine specs against materialized local evidence.")
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--max-specs", type=int, default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_engine_universe_with_generated_evidence(
        evidence_root=args.evidence_root,
        output_root=args.output_root,
        max_specs=args.max_specs,
    )
    if args.format == "report":
        print(render_full_engine_universe_run_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
