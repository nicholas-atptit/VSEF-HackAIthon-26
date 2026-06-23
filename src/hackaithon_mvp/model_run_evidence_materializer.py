"""Materialize compact engine evidence from a local training run."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.engine_catalog.catalog_schema import FEATURE_SCOPES, FEATURE_SETS
from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy, load_forecast_accuracy_rows
from src.hackaithon_mvp.static_evidence_loader import validate_evidence_records


CLAIM_BOUNDARY = {
    "materializes_local_training_outputs": True,
    "writes_require_explicit_roots": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_training": True,
    "no_model_update": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Evidence materialization only; generated rows remain local artifacts under the explicit output root."


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _validate_root(path: str | Path, label: str) -> Path:
    root = Path(path)
    allowed = (".tmp_full_model_run", ".tmp_performance_rescue", ".tmp_accuracy_maximization", ".tmp_forecast_repair")
    if not any(part.lower().startswith(allowed) for part in root.parts):
        raise ValueError(f"{label} must be under an explicit local temp model-run root")
    root.mkdir(parents=True, exist_ok=True)
    return root


def materialize_forecast_rows_from_training_run(*, run_root: str) -> dict:
    """Summarize generated forecast-vs-actual rows from a training run root."""

    root = Path(run_root)
    rows = _read_jsonl(root / "forecast_actual_rows.jsonl")
    by_model = Counter(str(row.get("model_id") or "missing") for row in rows)
    by_horizon = Counter(str(row.get("horizon") or "missing") for row in rows)
    by_target = Counter(str(row.get("target") or "missing") for row in rows)
    return {
        "materialization_status": "completed" if rows else "no_forecast_rows",
        "forecast_row_count": len(rows),
        "actual_row_count": len([row for row in rows if row.get("actual_direction") not in (None, "") or row.get("actual_return") not in (None, "")]),
        "rows_by_model": dict(sorted(by_model.items())),
        "rows_by_horizon": dict(sorted(by_horizon.items())),
        "rows_by_target": dict(sorted(by_target.items())),
        "forecast_rows_path": str(root / "forecast_actual_rows.jsonl"),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def materialize_model_diagnostics_from_training_run(*, run_root: str) -> dict:
    """Build compact model diagnostic summaries from a training run."""

    root = Path(run_root)
    summary = _read_json(root / "training_run_summary.json")
    diagnostics = []
    for result in summary.get("model_results", []) if isinstance(summary.get("model_results"), list) else []:
        diagnostics.append(
            {
                "model_key": result.get("model_key"),
                "model_family": result.get("model_family"),
                "target": result.get("target"),
                "horizon": result.get("horizon"),
                "training_status": result.get("training_status"),
                "tuning_status": result.get("tuning_status"),
                "train_rows": result.get("train_rows"),
                "validation_rows": result.get("validation_rows"),
                "selected_hyperparameters": result.get("selected_hyperparameters"),
                "selected_threshold": result.get("selected_threshold"),
                "pre_tune_validation_metrics": result.get("pre_tune_validation_metrics"),
                "post_tune_validation_metrics": result.get("post_tune_validation_metrics"),
            }
        )
    return {
        "materialization_status": "completed" if diagnostics else "no_model_diagnostics",
        "model_diagnostic_count": len(diagnostics),
        "model_diagnostics": diagnostics,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _dependency_result(key: str, source: str) -> dict[str, Any]:
    return {
        "dependency_id": key,
        "status": "completed",
        "source": source,
        "diagnostic_label": "neutral_or_uncertain",
        "claim_scope": "diagnostic_only",
    }


def _dependency_results(evidence_records: list[dict]) -> list[dict[str, Any]]:
    family_target_horizon: set[tuple[str, str, int]] = set()
    classification_target_horizon: set[tuple[str, int]] = set()
    for record in evidence_records:
        family = str(record.get("model_family"))
        target = str(record.get("target"))
        horizon = int(record.get("horizon"))
        family_target_horizon.add((family, target, horizon))
        if family == "classification":
            classification_target_horizon.add((target, horizon))
    dependencies: dict[str, dict[str, Any]] = {}
    for family, target, horizon in family_target_horizon:
        for scope in FEATURE_SCOPES:
            key = f"{family}.{target}.h{horizon}.{scope}"
            dependencies[key] = _dependency_result(key, "generated_baseline_family_output")
    for target, horizon in classification_target_horizon:
        for feature_set in FEATURE_SETS:
            key = f"support.evidence_strength.static_demo.{target}.h{horizon}.{feature_set}_classification"
            dependencies[key] = _dependency_result(key, "generated_support_output")
    return list(sorted(dependencies.values(), key=lambda item: item["dependency_id"]))


def materialize_engine_evidence_from_training_run(*, run_root: str, evidence_root: str) -> dict:
    """Write compact static evidence and dependency outputs for generated engine sweeps."""

    run_path = Path(run_root)
    evidence_path = _validate_root(evidence_root, "evidence_root")
    evidence_payload = _read_json(run_path / "model_evidence_records.json")
    records = evidence_payload.get("records", []) if isinstance(evidence_payload.get("records"), list) else []
    validated_records = validate_evidence_records(records) if records else []
    forecast_rows = _read_jsonl(run_path / "forecast_actual_rows.jsonl")
    diagnostics = materialize_model_diagnostics_from_training_run(run_root=str(run_path))["model_diagnostics"]
    dependencies = _dependency_results(validated_records)
    accuracy = evaluate_forecast_accuracy(forecast_rows)
    _write_json(evidence_path / "static_evidence.json", validated_records)
    _write_jsonl(evidence_path / "dependency_results.jsonl", dependencies)
    _write_jsonl(evidence_path / "forecast_actual_rows.jsonl", forecast_rows)
    _write_jsonl(evidence_path / "model_diagnostics.jsonl", diagnostics)
    _write_json(evidence_path / "accuracy_summary.json", accuracy)
    coverage: dict[str, Counter] = defaultdict(Counter)
    for record in validated_records:
        coverage["by_model_key"][str(record.get("model_key"))] += 1
        coverage["by_target"][str(record.get("target"))] += 1
        coverage["by_horizon"][str(record.get("horizon"))] += 1
        coverage["by_family"][str(record.get("model_family"))] += 1
    return {
        "materialization_status": "completed" if validated_records else "no_evidence_records",
        "evidence_root": str(evidence_path),
        "static_evidence_record_count": len(validated_records),
        "dependency_result_count": len(dependencies),
        "forecast_row_count": len(forecast_rows),
        "model_diagnostic_count": len(diagnostics),
        "accuracy_status": accuracy.get("accuracy_status"),
        "directional_accuracy": accuracy.get("global", {}).get("directional", {}).get("accuracy"),
        "balanced_accuracy": accuracy.get("global", {}).get("directional", {}).get("balanced_accuracy"),
        "coverage": {key: dict(counter) for key, counter in coverage.items()},
        "outputs": {
            "static_evidence": str(evidence_path / "static_evidence.json"),
            "dependency_results": str(evidence_path / "dependency_results.jsonl"),
            "forecast_actual_rows": str(evidence_path / "forecast_actual_rows.jsonl"),
            "model_diagnostics": str(evidence_path / "model_diagnostics.jsonl"),
            "accuracy_summary": str(evidence_path / "accuracy_summary.json"),
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_model_run_evidence_report(result: dict) -> str:
    """Render a compact materialization report."""

    lines = [
        "# Model Run Evidence Materialization",
        "",
        f"Materialization status: {result.get('materialization_status')}",
        f"Static evidence records: {result.get('static_evidence_record_count')}",
        f"Dependency results: {result.get('dependency_result_count')}",
        f"Forecast rows: {result.get('forecast_row_count')}",
        f"Model diagnostics: {result.get('model_diagnostic_count')}",
        f"Directional accuracy: {result.get('directional_accuracy')}",
        f"Balanced accuracy: {result.get('balanced_accuracy')}",
        "",
        "Boundary:",
        "Only compact generated evidence is written under the explicit evidence root.",
        "Raw generated artifacts remain untracked local outputs.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize compact evidence from a local training run.")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = materialize_engine_evidence_from_training_run(run_root=args.run_root, evidence_root=args.evidence_root)
    if args.format == "report":
        print(render_model_run_evidence_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
