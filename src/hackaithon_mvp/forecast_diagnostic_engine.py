"""Bounded forecast diagnostics over static MVP engine evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_runtime.engine_registry import EngineNotFoundError, EngineRegistry
from src.hackaithon_mvp.engine_runtime.engine_result import EngineResult
from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine
from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec
from src.hackaithon_mvp.static_evidence_loader import StaticEvidenceValidationError, load_static_evidence


FORECAST_DIAGNOSTIC_LABELS = frozenset(
    {
        "positive_bias",
        "negative_bias",
        "neutral_or_uncertain",
        "insufficient_evidence",
        "exploratory_only",
    }
)
BASELINE_STATUSES = frozenset(
    {
        "baseline_not_available",
        "below_baseline",
        "weak_edge",
        "meaningful_edge",
        "insufficient_evidence",
    }
)
EVIDENCE_STATUSES = frozenset(
    {
        "bounded_static_evidence",
        "missing_evidence",
        "scope_limited",
        "exploratory_only",
    }
)
SUPPORTED_METRIC_FIELDS = (
    "accuracy",
    "balanced_accuracy",
    "macro_accuracy",
    "baseline_accuracy",
    "baseline_balanced_accuracy",
    "coverage",
    "sample_count",
)
PRIMARY_METRIC_FIELDS = ("balanced_accuracy", "accuracy", "macro_accuracy")
BASELINE_METRIC_FIELDS = ("baseline_balanced_accuracy", "baseline_accuracy")
MEANINGFUL_EDGE_THRESHOLD = 0.02
WEAK_EDGE_THRESHOLD = 0.005
NON_CLAIM_TEXT = "Research diagnostic only; human review required."
MAX_DIAGNOSTIC_CONFIDENCE_WITHOUT_BASELINE_SUMMARY = 0.5


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, EngineResult):
        return value.to_dict()
    if isinstance(value, dict):
        return dict(value)
    return {}


def _nested_dict(value: dict[str, Any], key: str) -> dict[str, Any]:
    nested = value.get(key)
    return dict(nested) if isinstance(nested, dict) else {}


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    if number is None:
        return None
    return int(number)


def _first_metric(metrics: dict[str, Any], names: tuple[str, ...]) -> tuple[str | None, float | None]:
    for name in names:
        metric = _safe_float(metrics.get(name))
        if metric is not None:
            return name, metric
    return None, None


def _metric_pool(
    engine_payload: dict[str, Any],
    evidence_record: dict[str, Any] | None,
    baseline_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for source in (
        _nested_dict(engine_payload, "metrics"),
        evidence_record or {},
        _nested_dict(evidence_record or {}, "metrics"),
        baseline_summary or {},
        _nested_dict(baseline_summary or {}, "metrics"),
    ):
        for field in SUPPORTED_METRIC_FIELDS:
            if field in source and field not in metrics:
                metrics[field] = source[field]
    return metrics


def _snapshot_metrics(metrics: dict[str, Any], primary_name: str | None, baseline_name: str | None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for field in SUPPORTED_METRIC_FIELDS:
        value = metrics.get(field)
        numeric_value = _safe_float(value)
        if numeric_value is not None:
            snapshot[field] = numeric_value
    sample_count = _safe_int(metrics.get("sample_count"))
    if sample_count is not None:
        snapshot["sample_count"] = sample_count
    if primary_name:
        snapshot["primary_metric"] = primary_name
    if baseline_name:
        snapshot["baseline_metric"] = baseline_name
    if primary_name and baseline_name:
        edge = _safe_float(snapshot.get(primary_name))
        baseline = _safe_float(snapshot.get(baseline_name))
        if edge is not None and baseline is not None:
            snapshot["edge_vs_baseline"] = round(edge - baseline, 6)
    return snapshot


def _extract_identity(engine_payload: dict[str, Any], evidence_record: dict[str, Any] | None) -> dict[str, Any]:
    metadata = _nested_dict(engine_payload, "metadata")
    source = evidence_record or {}
    return {
        "engine_id": engine_payload.get("engine_id"),
        "model_key": metadata.get("model_key", source.get("model_key")),
        "model_family": metadata.get("model_family", source.get("model_family")),
        "target": metadata.get("target", source.get("target")),
        "horizon": metadata.get("horizon", source.get("horizon")),
    }


def _confidence(value: float, baseline_summary: dict[str, Any] | None) -> float:
    bounded = max(0.0, min(float(value), 1.0))
    if baseline_summary is None:
        bounded = min(bounded, MAX_DIAGNOSTIC_CONFIDENCE_WITHOUT_BASELINE_SUMMARY)
    return round(bounded, 6)


def _result(
    *,
    engine_payload: dict[str, Any],
    evidence_record: dict[str, Any] | None,
    forecast_diagnostic: str,
    confidence: float,
    baseline_status: str,
    evidence_status: str,
    metric_snapshot: dict[str, Any],
    diagnostic_explanation: str,
    claim_scope: str,
    baseline_summary: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    if forecast_diagnostic not in FORECAST_DIAGNOSTIC_LABELS:
        raise ValueError(f"unsupported forecast_diagnostic: {forecast_diagnostic}")
    if baseline_status not in BASELINE_STATUSES:
        raise ValueError(f"unsupported baseline_status: {baseline_status}")
    if evidence_status not in EVIDENCE_STATUSES:
        raise ValueError(f"unsupported evidence_status: {evidence_status}")

    identity = _extract_identity(engine_payload, evidence_record)
    return {
        **identity,
        "forecast_diagnostic": forecast_diagnostic,
        "confidence": _confidence(confidence, baseline_summary),
        "baseline_status": baseline_status,
        "evidence_status": evidence_status,
        "metric_snapshot": metric_snapshot,
        "diagnostic_explanation": diagnostic_explanation,
        "claim_scope": claim_scope,
        "human_review_required": True,
        "non_claim": NON_CLAIM_TEXT,
        "warnings": warnings,
    }


def run_forecast_diagnostic(
    engine_result: dict,
    evidence_record: dict | None = None,
    adapter_metadata: dict | None = None,
    baseline_summary: dict | None = None,
) -> dict:
    """Interpret static/local evidence into one bounded forecast diagnostic."""

    engine_payload = _as_dict(engine_result)
    evidence_payload = dict(evidence_record) if isinstance(evidence_record, dict) else None
    adapter_payload = dict(adapter_metadata) if isinstance(adapter_metadata, dict) else {}
    baseline_payload = dict(baseline_summary) if isinstance(baseline_summary, dict) and baseline_summary else None
    claim_scope_value = engine_payload.get("claim_scope")
    if not claim_scope_value and evidence_payload is not None:
        claim_scope_value = evidence_payload.get("claim_scope")
    if not claim_scope_value:
        claim_scope_value = adapter_payload.get("claim_scope", "diagnostic_only")
    claim_scope = str(claim_scope_value)
    warnings = list(engine_payload.get("warnings", []) or [])

    if engine_payload.get("status") == "skipped_missing_evidence":
        warnings.append("static evidence missing for engine result")
        return _result(
            engine_payload=engine_payload,
            evidence_record=evidence_payload,
            forecast_diagnostic="insufficient_evidence",
            confidence=0.0,
            baseline_status="insufficient_evidence",
            evidence_status="missing_evidence",
            metric_snapshot={},
            diagnostic_explanation="Static evidence is missing for this engine result.",
            claim_scope="evidence_insufficient",
            baseline_summary=baseline_payload,
            warnings=warnings,
        )

    if evidence_payload is None:
        warnings.append("static evidence record missing")
        return _result(
            engine_payload=engine_payload,
            evidence_record=None,
            forecast_diagnostic="insufficient_evidence",
            confidence=0.0,
            baseline_status="insufficient_evidence",
            evidence_status="missing_evidence",
            metric_snapshot={},
            diagnostic_explanation="No local static evidence record was available.",
            claim_scope="evidence_insufficient",
            baseline_summary=baseline_payload,
            warnings=warnings,
        )

    metrics = _metric_pool(engine_payload, evidence_payload, baseline_payload)
    primary_name, primary_metric = _first_metric(metrics, PRIMARY_METRIC_FIELDS)
    baseline_name, baseline_metric = _first_metric(metrics, BASELINE_METRIC_FIELDS)
    metric_snapshot = _snapshot_metrics(metrics, primary_name, baseline_name)

    if claim_scope == "exploratory_only":
        warnings.append("claim scope is exploratory only")
        return _result(
            engine_payload=engine_payload,
            evidence_record=evidence_payload,
            forecast_diagnostic="exploratory_only",
            confidence=0.25,
            baseline_status="insufficient_evidence" if baseline_metric is None else "weak_edge",
            evidence_status="exploratory_only",
            metric_snapshot=metric_snapshot,
            diagnostic_explanation="The static evidence is marked exploratory only.",
            claim_scope="exploratory_only",
            baseline_summary=baseline_payload,
            warnings=warnings,
        )

    if primary_metric is None:
        warnings.append("primary evidence metric missing")
        return _result(
            engine_payload=engine_payload,
            evidence_record=evidence_payload,
            forecast_diagnostic="neutral_or_uncertain",
            confidence=0.2,
            baseline_status="insufficient_evidence",
            evidence_status="scope_limited",
            metric_snapshot=metric_snapshot,
            diagnostic_explanation="Static evidence is present but lacks a primary metric.",
            claim_scope=claim_scope,
            baseline_summary=baseline_payload,
            warnings=warnings,
        )

    if baseline_metric is None:
        warnings.append("baseline metric unavailable")
        return _result(
            engine_payload=engine_payload,
            evidence_record=evidence_payload,
            forecast_diagnostic="neutral_or_uncertain",
            confidence=0.4,
            baseline_status="baseline_not_available",
            evidence_status="scope_limited",
            metric_snapshot=metric_snapshot,
            diagnostic_explanation="A primary metric is present, but no baseline metric is available.",
            claim_scope=claim_scope,
            baseline_summary=baseline_payload,
            warnings=warnings,
        )

    edge = primary_metric - baseline_metric
    if edge < 0.0:
        return _result(
            engine_payload=engine_payload,
            evidence_record=evidence_payload,
            forecast_diagnostic="negative_bias",
            confidence=0.55,
            baseline_status="below_baseline",
            evidence_status="bounded_static_evidence",
            metric_snapshot=metric_snapshot,
            diagnostic_explanation="The model metric is below the available baseline metric.",
            claim_scope=claim_scope,
            baseline_summary=baseline_payload,
            warnings=warnings,
        )
    if edge >= MEANINGFUL_EDGE_THRESHOLD:
        return _result(
            engine_payload=engine_payload,
            evidence_record=evidence_payload,
            forecast_diagnostic="positive_bias",
            confidence=0.65,
            baseline_status="meaningful_edge",
            evidence_status="bounded_static_evidence",
            metric_snapshot=metric_snapshot,
            diagnostic_explanation="The model metric is meaningfully above the available baseline metric.",
            claim_scope=claim_scope,
            baseline_summary=baseline_payload,
            warnings=warnings,
        )
    if edge >= WEAK_EDGE_THRESHOLD:
        baseline_status = "weak_edge"
        explanation = "The model metric is only weakly above the available baseline metric."
    else:
        baseline_status = "insufficient_evidence"
        explanation = "The model metric does not clear the weak edge threshold."
    return _result(
        engine_payload=engine_payload,
        evidence_record=evidence_payload,
        forecast_diagnostic="neutral_or_uncertain",
        confidence=0.45,
        baseline_status=baseline_status,
        evidence_status="bounded_static_evidence",
        metric_snapshot=metric_snapshot,
        diagnostic_explanation=explanation,
        claim_scope=claim_scope,
        baseline_summary=baseline_payload,
        warnings=warnings,
    )


def _matching_evidence(spec: EngineSpec, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        if (
            record.get("model_key") == spec.model_key
            and record.get("target") == spec.target
            and int(record.get("horizon", -1)) == spec.horizon
        ):
            return record
    return None


def _load_records(path: str | None) -> list[dict[str, Any]]:
    try:
        return load_static_evidence(Path(path)) if path else load_static_evidence()
    except (FileNotFoundError, StaticEvidenceValidationError, OSError):
        return []


def _resolve_spec(engine_id: str, catalog_dir: str | None = None) -> EngineSpec | None:
    try:
        return EngineRegistry.from_catalog_dir(catalog_dir).get(engine_id)
    except EngineNotFoundError:
        pass
    for spec in generate_baseline_catalog():
        if spec.engine_id == engine_id:
            return spec
    return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one bounded forecast diagnostic from static local evidence.")
    parser.add_argument("--engine-id", required=True)
    parser.add_argument("--catalog-dir", default=None)
    parser.add_argument("--evidence-path", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    records = _load_records(args.evidence_path)
    spec = _resolve_spec(args.engine_id, args.catalog_dir)
    if spec is None:
        diagnostic = run_forecast_diagnostic(
            {
                "engine_id": args.engine_id,
                "status": "skipped_missing_evidence",
                "claim_scope": "evidence_insufficient",
                "warnings": ["engine spec unavailable in static generated catalog"],
            },
            evidence_record=None,
        )
        print(json.dumps(diagnostic, indent=2, sort_keys=True))
        return 0

    evidence_record = _matching_evidence(spec, records)
    result = run_engine(spec, evidence_records=records)
    diagnostic = run_forecast_diagnostic(result.to_dict(), evidence_record=evidence_record)
    print(json.dumps(diagnostic, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
