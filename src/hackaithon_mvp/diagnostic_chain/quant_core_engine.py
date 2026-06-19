"""Layer 1: bounded static quant diagnostic summary."""

from __future__ import annotations

from collections import Counter

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine
from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec
from src.hackaithon_mvp.static_evidence_loader import load_static_evidence

from .chain_schema import (
    ALLOWED_QUANT_SIGNALS,
    NON_CLAIM_TEXT,
    QuantCoreOutput,
    assert_allowed,
    assert_no_forbidden_public_terms,
)

MAX_BASELINE_SAMPLE_SIZE = 500


def _matches_record(spec: EngineSpec, record: dict[str, object]) -> bool:
    return (
        record.get("model_key") == spec.model_key
        and record.get("target") == spec.target
        and int(record.get("horizon", -1)) == spec.horizon
    )


def _select_bounded_specs(
    specs: tuple[EngineSpec, ...],
    ticker_records: list[dict[str, object]],
    sample_size: int,
) -> list[EngineSpec]:
    selected: dict[str, EngineSpec] = {}

    for spec in specs:
        if len(selected) >= sample_size:
            break
        if any(_matches_record(spec, record) for record in ticker_records):
            selected[spec.engine_id] = spec

    for spec in specs:
        if len(selected) >= sample_size:
            break
        selected.setdefault(spec.engine_id, spec)

    return list(selected.values())


def _summarize_signal(label_counts: Counter[str], completed_count: int, checked_count: int) -> str:
    if completed_count == 0:
        return "insufficient_evidence"
    if checked_count == 0:
        return "insufficient_evidence"

    completion_ratio = completed_count / checked_count
    if completion_ratio < 0.05:
        return "neutral_or_uncertain"
    if label_counts.get("exploratory_only", 0) == completed_count:
        return "exploratory_only"
    if label_counts.get("positive_bias", 0) > label_counts.get("negative_bias", 0):
        return "positive_bias"
    if label_counts.get("negative_bias", 0) > label_counts.get("positive_bias", 0):
        return "negative_bias"
    return "neutral_or_uncertain"


def run_quant_core(ticker: str, sample_size: int = MAX_BASELINE_SAMPLE_SIZE) -> QuantCoreOutput:
    """Run a bounded set of generated baseline specs against local sample evidence."""

    normalized_ticker = ticker.strip().upper()
    bounded_sample_size = max(0, min(int(sample_size), MAX_BASELINE_SAMPLE_SIZE))
    records = load_static_evidence()
    ticker_records = [record for record in records if str(record.get("ticker", "")).upper() == normalized_ticker]
    specs = generate_baseline_catalog()
    selected_specs = _select_bounded_specs(specs, ticker_records, bounded_sample_size)

    completed_count = 0
    skipped_missing_evidence_count = 0
    label_counts: Counter[str] = Counter()

    for spec in selected_specs:
        result = run_engine(spec, evidence_records=ticker_records)
        if result.status == "completed":
            completed_count += 1
            label_counts[result.diagnostic_label] += 1
        elif result.status == "skipped_missing_evidence":
            skipped_missing_evidence_count += 1

    checked_count = len(selected_specs)
    quant_signal = _summarize_signal(label_counts, completed_count, checked_count)
    assert_allowed(quant_signal, ALLOWED_QUANT_SIGNALS, "quant_signal")

    warnings = [
        "static local sample evidence only",
        "provider access disabled",
        "model training disabled",
        "model inference disabled",
        "benchmark rerun disabled",
    ]
    if sample_size > MAX_BASELINE_SAMPLE_SIZE:
        warnings.append(f"sample size capped at {MAX_BASELINE_SAMPLE_SIZE}")
    if not ticker_records:
        warnings.append("no matching local sample evidence for ticker")
    if checked_count < int(sample_size):
        warnings.append("bounded sample exhausted available generated baseline specs")

    output: QuantCoreOutput = {
        "ticker": normalized_ticker,
        "quant_signal": quant_signal,
        "consensus_strength": round(completed_count / checked_count, 6) if checked_count else 0.0,
        "engine_count_checked": checked_count,
        "completed_count": completed_count,
        "skipped_missing_evidence_count": skipped_missing_evidence_count,
        "warnings": warnings,
        "non_claim": NON_CLAIM_TEXT,
    }
    assert_no_forbidden_public_terms(output)
    return output
