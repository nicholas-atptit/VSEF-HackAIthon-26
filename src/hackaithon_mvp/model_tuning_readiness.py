"""Readiness gate for local diagnostic tuning inputs."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import DIRECTIONAL_DIAGNOSTICS, load_forecast_actual_rows
from src.hackaithon_mvp.quant_core_accuracy_optimizer import split_rows_for_policy_validation


READINESS_STATUSES = (
    "not_ready_no_labeled_data",
    "ready_for_limited_policy_search_only",
    "ready_for_local_diagnostic_tuning",
)
SEARCH_PATTERNS = ("*.jsonl", "*.json", "*.csv")
DEFAULT_SEARCH_ROOTS = (".", ".tmp_tuning_inputs", ".tmp_self_improve_inputs")
LIKELY_LABELED_NAME_TOKENS = ("forecast_actual", "forecast-vs-actual", "predicted_vs_actual", "actual_rows")
MAX_CANDIDATE_FILES = 200
MAX_CANDIDATE_BYTES = 5_000_000
MAX_WALK_DIRS = 1_000
MAX_WALK_DEPTH = 4
EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".pytest-tmp",
    "data",
    "archive",
    "models",
    "packaged_docs",
    "reports",
    "catalogs",
    "cache",
    "node_modules",
    ".venv",
}
MIN_POLICY_ROWS = 6
MIN_DIAGNOSTIC_ROWS = 60
CLAIM_BOUNDARY = {
    "readiness_gate_only": True,
    "no_training": True,
    "no_model_update": True,
    "no_fine_tuning": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_benchmark_rerun": True,
    "writes_files_by_default": False,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local tuning readiness gate only; no tuning or model update is run by default."


def _is_ignored_or_generated(path: Path, root_path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    root_parts = {part.lower() for part in root_path.parts}
    if ".git" in parts or "__pycache__" in parts or ".pytest_cache" in parts or ".pytest-tmp" in parts:
        if ".pytest-tmp" in parts and ".pytest-tmp" in root_parts:
            return False
        return True
    if "data" in parts or "archive" in parts or "models" in parts or "packaged_docs" in parts:
        return True
    if "reports" in parts or "catalogs" in parts or "cache" in parts:
        return True
    return False


def _candidate_paths(search_roots: tuple[str, ...]) -> tuple[Path, ...]:
    paths: list[Path] = []
    for root in search_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        walked_dirs = 0
        for dirpath, dirnames, filenames in os.walk(root_path):
            walked_dirs += 1
            current_path = Path(dirpath)
            try:
                depth = len(current_path.relative_to(root_path).parts)
            except ValueError:
                depth = MAX_WALK_DEPTH + 1
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname.lower() not in EXCLUDED_DIR_NAMES
                and not dirname.startswith(".tmp_")
                and not dirname.startswith(".pytest-tmp")
            ]
            if depth >= MAX_WALK_DEPTH:
                dirnames[:] = []
            if walked_dirs > MAX_WALK_DIRS:
                break
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.suffix.lower() not in {".jsonl", ".json", ".csv"}:
                    continue
                if not path.is_file() or _is_ignored_or_generated(path, root_path):
                    continue
                lowered_name = path.name.lower()
                if not any(token in lowered_name for token in LIKELY_LABELED_NAME_TOKENS):
                    continue
                try:
                    if path.stat().st_size > MAX_CANDIDATE_BYTES:
                        continue
                except OSError:
                    continue
                paths.append(path)
                if len(paths) >= MAX_CANDIDATE_FILES:
                    return tuple(sorted(dict.fromkeys(paths), key=lambda item: str(item)))
    return tuple(sorted(dict.fromkeys(paths), key=lambda item: str(item)))


def _inspect_path(path: Path) -> dict[str, Any]:
    try:
        rows = load_forecast_actual_rows(str(path))
    except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        return {
            "path": str(path),
            "rows_total": 0,
            "valid_labeled_rows": 0,
            "load_status": "not_forecast_actual_rows",
            "errors": [type(exc).__name__],
        }
    directional_rows = [row for row in rows if row["forecast_diagnostic"] in DIRECTIONAL_DIAGNOSTICS]
    by_ticker = Counter(str(row.get("ticker", "missing")) for row in rows)
    by_horizon = Counter(str(row.get("horizon_steps", "missing")) for row in rows)
    feature_columns = sorted(
        field
        for field in ("diagnostic_score", "confidence", "coverage_ratio", "model_family", "risk_level", "route")
        if any(row.get(field) not in (None, "") for row in rows)
    )
    split = split_rows_for_policy_validation(rows) if len(rows) > 1 else {"split_method": "unavailable", "warnings": []}
    temporal_split_possible = str(split.get("split_method", "")).startswith("chronological_")
    return {
        "path": str(path),
        "rows_total": len(rows),
        "valid_labeled_rows": len(rows),
        "directional_rows": len(directional_rows),
        "ticker_count": len(by_ticker),
        "horizon_count": len(by_horizon),
        "rows_by_ticker": dict(sorted(by_ticker.items())),
        "rows_by_horizon": dict(sorted(by_horizon.items())),
        "feature_columns": feature_columns,
        "temporal_split_possible": temporal_split_possible,
        "split_method": split.get("split_method"),
        "load_status": "forecast_actual_rows",
        "errors": [],
        "warnings": list(split.get("warnings", [])),
    }


def inspect_local_tuning_inputs(search_roots: tuple[str, ...] = DEFAULT_SEARCH_ROOTS) -> dict:
    """Inspect local candidate artifacts without tuning or writing outputs."""

    paths = _candidate_paths(tuple(search_roots))
    inspected = tuple(_inspect_path(path) for path in paths)
    labeled = tuple(item for item in inspected if item["load_status"] == "forecast_actual_rows")
    row_count = sum(int(item["valid_labeled_rows"]) for item in labeled)
    temporal_ready = any(item.get("temporal_split_possible") for item in labeled)
    feature_columns = sorted({field for item in labeled for field in item.get("feature_columns", [])})
    return {
        "inspection_status": "completed",
        "search_roots": list(search_roots),
        "candidate_file_count": len(paths),
        "labeled_artifact_count": len(labeled),
        "total_labeled_rows": row_count,
        "temporal_split_possible": temporal_ready,
        "feature_columns": feature_columns,
        "artifacts": list(inspected),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def run_model_tuning_readiness_gate(search_roots: tuple[str, ...] = DEFAULT_SEARCH_ROOTS) -> dict:
    """Classify whether local labeled evidence is sufficient for bounded tuning work."""

    inspection = inspect_local_tuning_inputs(search_roots=search_roots)
    row_count = int(inspection["total_labeled_rows"])
    has_features = bool(inspection["feature_columns"])
    temporal_ready = bool(inspection["temporal_split_possible"])
    blockers: list[str] = []
    if row_count == 0:
        blockers.append("local_labeled_forecast_actual_rows_missing")
    if row_count and not temporal_ready:
        blockers.append("temporal_validation_split_missing")
    if row_count and not has_features:
        blockers.append("feature_columns_missing")
    if row_count and row_count < MIN_POLICY_ROWS:
        blockers.append("too_few_rows_for_policy_search")

    if row_count == 0:
        status = "not_ready_no_labeled_data"
    elif row_count >= MIN_DIAGNOSTIC_ROWS and temporal_ready and has_features:
        status = "ready_for_local_diagnostic_tuning"
    elif row_count >= MIN_POLICY_ROWS and temporal_ready:
        status = "ready_for_limited_policy_search_only"
    else:
        status = "not_ready_no_labeled_data"

    if status == "ready_for_local_diagnostic_tuning":
        allowed_next_step = "human-reviewed local diagnostic threshold tuning only"
    elif status == "ready_for_limited_policy_search_only":
        allowed_next_step = "limited policy threshold search with explicit temp output only"
    else:
        allowed_next_step = "collect local labeled forecast-vs-actual rows before tuning"

    return {
        "readiness_status": status,
        "checks": {
            "local_labeled_rows_available": row_count > 0,
            "enough_rows_by_ticker_horizon": row_count >= MIN_POLICY_ROWS,
            "temporal_split_possible": temporal_ready,
            "feature_columns_available": has_features,
            "no_data_leakage_review_required": True,
            "objective_declared": True,
            "output_path_must_be_explicit_tmp": True,
            "human_review_required": True,
        },
        "blocking_reasons": blockers,
        "inspection": inspection,
        "allowed_next_step": allowed_next_step,
        "unsafe_or_deferred_items": [
            "no model training by default",
            "no model fine-tuning",
            "no generated tuning output without explicit .tmp_tuning path",
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_model_tuning_readiness_report(result: dict) -> str:
    """Render a compact tuning readiness report."""

    inspection = result.get("inspection", {}) if isinstance(result.get("inspection"), dict) else {}
    blocking_lines = [f"- {reason}" for reason in result.get("blocking_reasons", [])] or ["- none"]
    lines = [
        "# Model Tuning Readiness",
        "",
        f"Readiness status: {result.get('readiness_status')}",
        f"Labeled artifacts: {inspection.get('labeled_artifact_count')}",
        f"Total labeled rows: {inspection.get('total_labeled_rows')}",
        f"Temporal split possible: {inspection.get('temporal_split_possible')}",
        f"Feature columns: {', '.join(inspection.get('feature_columns', []) or ['none'])}",
        f"Allowed next step: {result.get('allowed_next_step')}",
        "",
        "Blocking reasons:",
        *blocking_lines,
        "",
        "Boundary:",
        "Readiness gate only; no training, model update, external data access, or benchmark rerun is performed.",
        "Generated tuning output requires an explicit .tmp_tuning path.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect local tuning readiness without running tuning.")
    parser.add_argument("--search-root", action="append", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    roots = tuple(args.search_root) if args.search_root else DEFAULT_SEARCH_ROOTS
    result = run_model_tuning_readiness_gate(search_roots=roots)
    if args.format == "report":
        print(render_model_tuning_readiness_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
