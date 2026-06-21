"""Static/local forecast diagnostic sweep over generated engine specs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_catalog.stack_catalog_generator import generate_stack_catalog
from src.hackaithon_mvp.engine_catalog.support_catalog_generator import generate_support_catalog
from src.hackaithon_mvp.engine_runtime.engine_result import EngineResult
from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine
from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec
from src.hackaithon_mvp.forecast_diagnostic_engine import run_forecast_diagnostic
from src.hackaithon_mvp.static_evidence_loader import StaticEvidenceValidationError, load_static_evidence


EXPECTED_ENGINE_UNIVERSE_TOTAL = 77_850
CLAIM_BOUNDARY = {
    "research_only": True,
    "diagnostic_only": True,
    "baseline_ml_only": True,
    "human_review_required": True,
    "static_local_evidence_only": True,
    "writes_files_by_default": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_enabled": False,
    "live_inference_enabled": False,
    "benchmark_rerun": False,
    "market_performance_claim": False,
}
CLAIM_BOUNDARY_TEXT = (
    "Static/local diagnostic execution over generated engine specs; "
    "human review required."
)
NON_CLAIM_TEXT = (
    "This sweep does not train models, fetch data, call providers, run live inference, "
    "rerun benchmarks, or claim market performance."
)
_MISSING_VALUE = "not_available"


def _validate_limit(limit: int | None) -> None:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative when provided")


def _catalog_sources(include_baseline: bool, include_auxiliary: bool, include_stack: bool) -> tuple[dict[str, Any], ...]:
    sources: list[dict[str, Any]] = []
    if include_baseline:
        sources.append(
            {
                "catalog_key": "baseline",
                "public_name": "baseline",
                "module": "src.hackaithon_mvp.engine_catalog.baseline_catalog_generator",
                "function": "generate_baseline_catalog",
                "generator": generate_baseline_catalog,
            }
        )
    if include_auxiliary:
        sources.append(
            {
                "catalog_key": "auxiliary",
                "public_name": "auxiliary",
                "module": "src.hackaithon_mvp.engine_catalog.support_catalog_generator",
                "function": "generate_support_catalog",
                "generator": generate_support_catalog,
            }
        )
    if include_stack:
        sources.append(
            {
                "catalog_key": "stack",
                "public_name": "stack",
                "module": "src.hackaithon_mvp.engine_catalog.stack_catalog_generator",
                "function": "generate_stack_catalog",
                "generator": generate_stack_catalog,
            }
        )
    return tuple(sources)


def _iter_selected_specs(
    *,
    include_baseline: bool,
    include_auxiliary: bool,
    include_stack: bool,
) -> Iterable[EngineSpec]:
    for source in _catalog_sources(include_baseline, include_auxiliary, include_stack):
        yield from source["generator"]()


def _distribution(counter: Counter[str]) -> dict[str, int]:
    return {
        key: count
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        if count
    }


def _field_value(value: Any) -> str:
    if value is None or value == "":
        return _MISSING_VALUE
    return str(value)


def _public_engine_type(engine_type: str | None) -> str | None:
    if engine_type == "support":
        return "auxiliary"
    return engine_type


def _public_engine_id(spec: EngineSpec) -> str:
    public_id = spec.engine_id
    if spec.engine_type == "support" and spec.engine_id.startswith("support."):
        public_id = "auxiliary." + spec.engine_id.removeprefix("support.")
    return public_id.replace("support", "auxiliary")


def build_engine_universe_sweep_plan(
    *,
    include_baseline: bool = True,
    include_auxiliary: bool = True,
    include_stack: bool = True,
    limit: int | None = None,
) -> dict:
    """Discover generated engine specs and return a no-write sweep plan."""

    _validate_limit(limit)
    catalog_entries: list[dict[str, Any]] = []
    total = 0
    for source in _catalog_sources(include_baseline, include_auxiliary, include_stack):
        specs = source["generator"]()
        count = len(specs)
        total += count
        catalog_entries.append(
            {
                "catalog_key": source["catalog_key"],
                "public_name": source["public_name"],
                "module": source["module"],
                "function": source["function"],
                "spec_count": count,
                "returns_tuple": isinstance(specs, tuple),
                "streaming_generator_style": False,
                "runner_available": True,
                "first_engine_id": specs[0].engine_id if specs else None,
            }
        )

    planned_attempts = total if limit is None else min(limit, total)
    return {
        "plan_status": "ready",
        "total_specs_discovered": total,
        "expected_total_specs": EXPECTED_ENGINE_UNIVERSE_TOTAL,
        "expected_total_match": total == EXPECTED_ENGINE_UNIVERSE_TOTAL,
        "planned_attempts": planned_attempts,
        "limit": limit,
        "include_baseline": include_baseline,
        "include_auxiliary": include_auxiliary,
        "include_stack": include_stack,
        "catalogs": catalog_entries,
        "writes_files_by_default": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "claim_boundary_text": CLAIM_BOUNDARY_TEXT,
        "non_claim": NON_CLAIM_TEXT,
    }


def _load_evidence_records() -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    try:
        return load_static_evidence(), ()
    except (FileNotFoundError, OSError, StaticEvidenceValidationError) as exc:
        return [], (f"static evidence load failed: {type(exc).__name__}",)


def _matching_evidence(spec: EngineSpec, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        try:
            horizon = int(record.get("horizon", -1))
        except (TypeError, ValueError):
            horizon = -1
        if record.get("model_key") == spec.model_key and record.get("target") == spec.target and horizon == spec.horizon:
            return record
    return None


def _skip_reason(engine_result: EngineResult | None, warnings: list[str], status: str) -> str | None:
    if status == "completed":
        return None
    if warnings:
        return warnings[0]
    if engine_result is not None and engine_result.status != "completed":
        return engine_result.status
    if status == "failed":
        return "engine execution failed"
    return None


def _compact_failure_result(spec: EngineSpec, exc: BaseException) -> dict[str, Any]:
    warning = f"engine sweep failure: {type(exc).__name__}"
    return {
        "engine_id": _public_engine_id(spec),
        "engine_family": spec.model_family,
        "engine_type": _public_engine_type(spec.engine_type),
        "model_key": spec.model_key,
        "target": spec.target,
        "horizon": spec.horizon,
        "feature_set": spec.feature_set,
        "policy": spec.policy,
        "execution_status": "failed",
        "forecast_diagnostic": None,
        "route": None,
        "risk_level": None,
        "skip_reason": warning,
        "warning_count": 1,
        "warnings": [warning],
    }


def _compact_engine_result(spec: EngineSpec, evidence_records: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    engine_result = run_engine(spec, evidence_records=evidence_records)
    engine_payload = engine_result.to_dict()
    evidence_record = _matching_evidence(spec, evidence_records) if spec.engine_type == "baseline" else None
    diagnostic = run_forecast_diagnostic(engine_payload, evidence_record=evidence_record)
    warnings.extend(str(warning) for warning in engine_payload.get("warnings", []) or [])
    warnings.extend(str(warning) for warning in diagnostic.get("warnings", []) or [])

    route = None
    risk_level = None
    warnings.append("route unavailable in engine-result scope")
    warnings.append("risk level unavailable in engine-result scope")
    status = str(engine_result.status)
    return {
        "engine_id": _public_engine_id(spec),
        "engine_family": spec.model_family,
        "engine_type": _public_engine_type(spec.engine_type),
        "model_key": spec.model_key,
        "target": spec.target,
        "horizon": spec.horizon,
        "feature_set": spec.feature_set,
        "policy": spec.policy,
        "execution_status": status,
        "forecast_diagnostic": diagnostic.get("forecast_diagnostic"),
        "route": route,
        "risk_level": risk_level,
        "skip_reason": _skip_reason(engine_result, warnings, status),
        "warning_count": len(warnings),
        "warnings": list(dict.fromkeys(warnings)),
    }


def _empty_summary(total_specs_discovered: int, limit: int | None, sample_size: int) -> dict[str, Any]:
    return {
        "sweep_status": "completed",
        "total_specs_discovered": total_specs_discovered,
        "total_specs_attempted": 0,
        "completed_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "diagnostic_distribution": {},
        "route_distribution": {},
        "risk_distribution": {},
        "family_distribution": {},
        "horizon_distribution": {},
        "skip_reason_distribution": {},
        "coverage_ratio": 0.0,
        "failure_ratio": 0.0,
        "representative_samples": [],
        "sample_size": sample_size,
        "limit": limit,
        "claim_boundary": CLAIM_BOUNDARY_TEXT,
        "claim_boundary_flags": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "writes_files_by_default": False,
    }


def _sample_result(
    samples: list[dict[str, Any]],
    seen_sample_keys: set[tuple[str, str, str]],
    result: dict[str, Any],
    sample_size: int,
) -> None:
    if sample_size <= 0:
        return
    duplicate_floor = min(sample_size, 5)
    key = (
        str(result.get("engine_type") or _MISSING_VALUE),
        str(result.get("execution_status") or _MISSING_VALUE),
        str(result.get("forecast_diagnostic") or _MISSING_VALUE),
    )
    if len(samples) < sample_size and key not in seen_sample_keys:
        samples.append({k: v for k, v in result.items() if k != "warnings"})
        seen_sample_keys.add(key)
    elif len(samples) < duplicate_floor:
        samples.append({k: v for k, v in result.items() if k != "warnings"})


def summarize_engine_universe_sweep(results: tuple[dict, ...]) -> dict:
    """Summarize compact per-engine sweep records."""

    attempted = len(results)
    summary = _empty_summary(attempted, None, 25)
    diagnostic_counter: Counter[str] = Counter()
    route_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    horizon_counter: Counter[str] = Counter()
    skip_counter: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    seen_sample_keys: set[tuple[str, str, str]] = set()
    completed = 0
    skipped = 0
    failed = 0

    for result in results:
        status = str(result.get("execution_status") or _MISSING_VALUE)
        if status == "completed":
            completed += 1
        elif status == "failed" or status.startswith("failed"):
            failed += 1
        else:
            skipped += 1
        diagnostic_counter[_field_value(result.get("forecast_diagnostic"))] += 1
        route_counter[_field_value(result.get("route"))] += 1
        risk_counter[_field_value(result.get("risk_level"))] += 1
        family_counter[_field_value(result.get("engine_family"))] += 1
        horizon_counter[_field_value(result.get("horizon"))] += 1
        reason = result.get("skip_reason")
        if reason:
            skip_counter[str(reason)] += 1
        _sample_result(samples, seen_sample_keys, result, 25)

    summary.update(
        {
            "sweep_status": "completed_with_engine_failures" if failed else "completed",
            "total_specs_attempted": attempted,
            "completed_count": completed,
            "skipped_count": skipped,
            "failed_count": failed,
            "diagnostic_distribution": _distribution(diagnostic_counter),
            "route_distribution": _distribution(route_counter),
            "risk_distribution": _distribution(risk_counter),
            "family_distribution": _distribution(family_counter),
            "horizon_distribution": _distribution(horizon_counter),
            "skip_reason_distribution": _distribution(skip_counter),
            "coverage_ratio": round(completed / attempted, 6) if attempted else 0.0,
            "failure_ratio": round(failed / attempted, 6) if attempted else 0.0,
            "representative_samples": samples,
        }
    )
    return summary


def run_engine_universe_forecast_sweep(
    *,
    limit: int | None = None,
    include_baseline: bool = True,
    include_auxiliary: bool = True,
    include_stack: bool = True,
    sample_size: int = 25,
) -> dict:
    """Run the static/local sweep and return a compact summary."""

    _validate_limit(limit)
    plan = build_engine_universe_sweep_plan(
        include_baseline=include_baseline,
        include_auxiliary=include_auxiliary,
        include_stack=include_stack,
        limit=limit,
    )
    catalog_counts = {
        str(entry["public_name"]): int(entry["spec_count"])
        for entry in plan.get("catalogs", [])
    }
    evidence_records, evidence_warnings = _load_evidence_records()
    summary = _empty_summary(int(plan["total_specs_discovered"]), limit, sample_size)
    diagnostic_counter: Counter[str] = Counter()
    route_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    horizon_counter: Counter[str] = Counter()
    skip_counter: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    seen_sample_keys: set[tuple[str, str, str]] = set()
    completed = 0
    skipped = 0
    failed = 0
    attempted = 0

    for spec in _iter_selected_specs(
        include_baseline=include_baseline,
        include_auxiliary=include_auxiliary,
        include_stack=include_stack,
    ):
        if limit is not None and attempted >= limit:
            break
        attempted += 1
        try:
            result = _compact_engine_result(spec, evidence_records)
            if evidence_warnings:
                result["warnings"] = list(result.get("warnings", [])) + list(evidence_warnings)
                result["warning_count"] = len(result["warnings"])
        except Exception as exc:  # noqa: BLE001 - per-engine isolation is intentional here.
            result = _compact_failure_result(spec, exc)
        status = str(result.get("execution_status") or _MISSING_VALUE)
        if status == "completed":
            completed += 1
        elif status == "failed" or status.startswith("failed"):
            failed += 1
        else:
            skipped += 1
        diagnostic_counter[_field_value(result.get("forecast_diagnostic"))] += 1
        route_counter[_field_value(result.get("route"))] += 1
        risk_counter[_field_value(result.get("risk_level"))] += 1
        family_counter[_field_value(result.get("engine_family"))] += 1
        horizon_counter[_field_value(result.get("horizon"))] += 1
        reason = result.get("skip_reason")
        if reason:
            skip_counter[str(reason)] += 1
        _sample_result(samples, seen_sample_keys, result, sample_size)

    summary.update(
        {
            "sweep_status": "completed_with_engine_failures" if failed else "completed",
            "total_specs_attempted": attempted,
            "completed_count": completed,
            "skipped_count": skipped,
            "failed_count": failed,
            "diagnostic_distribution": _distribution(diagnostic_counter),
            "route_distribution": _distribution(route_counter),
            "risk_distribution": _distribution(risk_counter),
            "family_distribution": _distribution(family_counter),
            "horizon_distribution": _distribution(horizon_counter),
            "skip_reason_distribution": _distribution(skip_counter),
            "coverage_ratio": round(completed / attempted, 6) if attempted else 0.0,
            "failure_ratio": round(failed / attempted, 6) if attempted else 0.0,
            "representative_samples": samples,
            "catalog_counts": catalog_counts,
        }
    )
    return summary


def _top_lines(title: str, distribution: dict[str, int], limit: int = 8) -> list[str]:
    lines = [title]
    if not distribution:
        return lines + ["- none"]
    return lines + [f"- {key}: {value}" for key, value in list(distribution.items())[:limit]]


def render_engine_universe_sweep_report(summary: dict) -> str:
    """Render a compact public-safe sweep summary."""

    lines = [
        "# Engine Universe Forecast Diagnostic Sweep",
        "",
        f"Status: {summary.get('sweep_status')}",
        f"Total specs discovered: {summary.get('total_specs_discovered')}",
        f"Total specs attempted: {summary.get('total_specs_attempted')}",
        f"Completed specs: {summary.get('completed_count')}",
        f"Skipped specs: {summary.get('skipped_count')}",
        f"Failed specs: {summary.get('failed_count')}",
        f"Evidence coverage ratio: {summary.get('coverage_ratio')}",
        f"Failure ratio: {summary.get('failure_ratio')}",
        "",
        *_top_lines("Diagnostic label distribution:", summary.get("diagnostic_distribution", {})),
        "",
        *_top_lines("Route distribution:", summary.get("route_distribution", {})),
        "",
        *_top_lines("Risk distribution:", summary.get("risk_distribution", {})),
        "",
        *_top_lines("Model family distribution:", summary.get("family_distribution", {})),
        "",
        *_top_lines("Horizon distribution:", summary.get("horizon_distribution", {})),
        "",
        *_top_lines("Top skip reasons:", summary.get("skip_reason_distribution", {}), limit=5),
        "",
        "Representative samples:",
    ]
    samples = summary.get("representative_samples", []) or []
    if not samples:
        lines.append("- none")
    for sample in samples[: int(summary.get("sample_size") or 25)]:
        lines.append(
            "- "
            f"{sample.get('engine_id')} | "
            f"status={sample.get('execution_status')} | "
            f"diagnostic={sample.get('forecast_diagnostic') or _MISSING_VALUE} | "
            f"route={sample.get('route') or _MISSING_VALUE} | "
            f"risk={sample.get('risk_level') or _MISSING_VALUE} | "
            f"skip={sample.get('skip_reason') or 'none'}"
        )
    lines.extend(
        [
            "",
            "Boundary:",
            str(summary.get("claim_boundary", CLAIM_BOUNDARY_TEXT)),
            str(summary.get("non_claim", NON_CLAIM_TEXT)),
            "Raw sweep outputs are generated artifacts and are not written by default.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_summary(summary: dict, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a static/local engine universe forecast diagnostic sweep.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--full", action="store_true", help="Attempt every discovered generated engine spec.")
    parser.add_argument("--format", choices=("json", "report"), default="report")
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument("--exclude-baseline", action="store_true")
    parser.add_argument("--exclude-auxiliary", action="store_true")
    parser.add_argument("--exclude-stack", action="store_true")
    parser.add_argument("--write-summary", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    limit = None if args.full else args.limit
    try:
        summary = run_engine_universe_forecast_sweep(
            limit=limit,
            include_baseline=not args.exclude_baseline,
            include_auxiliary=not args.exclude_auxiliary,
            include_stack=not args.exclude_stack,
            sample_size=args.sample_size,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.write_summary:
        _write_summary(summary, args.write_summary)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    else:
        print(render_engine_universe_sweep_report(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
