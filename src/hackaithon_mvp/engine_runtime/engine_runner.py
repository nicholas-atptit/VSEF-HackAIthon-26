"""Static-evidence MVP runner for one generated engine spec."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from src.hackaithon_mvp.static_evidence_loader import load_static_evidence

from .dependency_policy import dependency_lineage, missing_dependencies
from .engine_registry import EngineNotFoundError, EngineRegistry
from .engine_result import EngineResult
from .engine_spec import EngineSpec
from .output_store import EngineOutputStore


def _matched_static_evidence(spec: EngineSpec, records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if record.get("model_key") == spec.model_key
        and record.get("target") == spec.target
        and int(record.get("horizon", -1)) == spec.horizon
    ]


def _baseline_result(spec: EngineSpec, evidence_records: list[dict[str, object]] | None) -> EngineResult:
    records = evidence_records if evidence_records is not None else load_static_evidence()
    matches = _matched_static_evidence(spec, records)
    if not matches:
        return EngineResult(
            engine_id=spec.engine_id,
            status="skipped_missing_evidence",
            diagnostic_label="insufficient_evidence",
            confidence=0.0,
            risk_flags=("static_evidence_gap",),
            metrics={"matched_static_records": 0},
            claim_scope="evidence_insufficient",
            warnings=("no matching static evidence for model target horizon",),
            metadata={
                "run_mode": spec.run_mode,
                "model_key": spec.model_key,
                "target": spec.target,
                "horizon": spec.horizon,
            },
        )

    label = "exploratory_only" if spec.claim_scope == "exploratory_only" else "neutral_or_uncertain"
    return EngineResult(
        engine_id=spec.engine_id,
        status="completed",
        diagnostic_label=label,
        confidence=0.25,
        risk_flags=("static_evidence_only",),
        metrics={"matched_static_records": len(matches)},
        claim_scope=spec.claim_scope,
        warnings=("static MVP result uses local sample evidence only",),
        metadata={
            "run_mode": spec.run_mode,
            "model_key": spec.model_key,
            "model_family": spec.model_family,
            "target": spec.target,
            "horizon": spec.horizon,
            "matched_record_ids": [str(record.get("record_id")) for record in matches],
        },
    )


def _dependency_result(
    spec: EngineSpec,
    dependency_results: Mapping[str, EngineResult | dict[str, object]] | None,
) -> EngineResult:
    missing = missing_dependencies(spec, dependency_results)
    if missing:
        return EngineResult(
            engine_id=spec.engine_id,
            status="skipped_missing_dependency",
            diagnostic_label="insufficient_evidence",
            confidence=0.0,
            risk_flags=("dependency_output_gap",),
            metrics={"required_dependencies": len(spec.dependencies), "missing_dependencies": len(missing)},
            dependencies_used=dependency_lineage(spec, dependency_results),
            claim_scope="evidence_insufficient",
            warnings=("required dependency outputs are unavailable",),
            metadata={"run_mode": spec.run_mode, "engine_type": spec.engine_type},
        )

    used = dependency_lineage(spec, dependency_results)
    return EngineResult(
        engine_id=spec.engine_id,
        status="completed",
        diagnostic_label="exploratory_only" if spec.engine_type == "stack" else "neutral_or_uncertain",
        confidence=0.2,
        risk_flags=("derived_from_dependency_outputs",),
        metrics={"dependencies_used": len(used)},
        dependencies_used=used,
        claim_scope=spec.claim_scope,
        warnings=("static MVP dependency result only",),
        metadata={"run_mode": spec.run_mode, "engine_type": spec.engine_type},
    )


def run_engine(
    spec: EngineSpec,
    *,
    evidence_records: list[dict[str, object]] | None = None,
    dependency_results: Mapping[str, EngineResult | dict[str, object]] | None = None,
) -> EngineResult:
    if spec.run_mode != "static_evidence_mvp":
        return EngineResult(
            engine_id=spec.engine_id,
            status="blocked_by_claim_boundary",
            diagnostic_label="insufficient_evidence",
            confidence=0.0,
            risk_flags=("unsupported_run_mode",),
            claim_scope="evidence_insufficient",
            warnings=("only static_evidence_mvp is allowed",),
            metadata={"run_mode": spec.run_mode},
        )
    if spec.engine_type == "baseline":
        return _baseline_result(spec, evidence_records)
    return _dependency_result(spec, dependency_results)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one HackAIthon MVP engine in static evidence mode.")
    parser.add_argument("--engine-id", required=True)
    parser.add_argument("--catalog-dir", default=None)
    parser.add_argument("--evidence-path", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--write-output", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        spec = EngineRegistry.from_catalog_dir(args.catalog_dir).get(args.engine_id)
    except EngineNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    evidence_records = load_static_evidence(Path(args.evidence_path)) if args.evidence_path else None
    result = run_engine(spec, evidence_records=evidence_records)
    if args.write_output:
        run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        store = EngineOutputStore(run_id)
        store.write_manifest({"engine_id": spec.engine_id})
        store.append_result(result)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
