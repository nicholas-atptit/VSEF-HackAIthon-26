"""Discover local forecast-vs-actual artifacts without computing accuracy."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = (".jsonl", ".json", ".csv", ".parquet")
MAX_DISCOVERY_FILES = 400
MAX_INSPECT_BYTES = 5_000_000
MAX_TEXT_SAMPLE_BYTES = 256_000
MAX_WALK_DIRS = 2_000
MAX_WALK_DEPTH = 5
EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".pytest-tmp",
    "cache",
    "caches",
    "tmp",
    "temp",
    "artifacts",
    "reports",
    "catalogs",
    "configs",
    "secrets",
    "node_modules",
    "packaged_docs",
}
EXCLUDED_PREFIXES = (".tmp_", ".pytest-tmp")
LIKELY_NAME_TOKENS = (
    "forecast",
    "actual",
    "evaluation",
    "diagnostic",
    "ohlcv",
    "bars",
    "policy",
    "registry",
    "prediction",
    "outcome",
)
FORECAST_ALIASES = {
    "predicted_direction",
    "y_pred",
    "pred_label",
    "forecast_diagnostic",
    "predicted_return",
    "forecast_return",
    "predicted_probability",
    "prob_up",
    "score",
}
ACTUAL_ALIASES = {
    "actual_direction",
    "y_true",
    "actual_label",
    "actual_direction_label",
    "actual_return",
    "realized_return",
    "actual_future_return",
}
IDENTITY_ALIASES = {"ticker", "symbol"}
MODEL_ALIASES = {"model_id", "model_key", "engine_id", "model", "model_name"}
HORIZON_ALIASES = {"horizon", "horizon_steps"}
TIME_ALIASES = {"forecast_timestamp", "prediction_timestamp", "asof", "date", "datetime", "timestamp"}
PROBABILITY_ALIASES = {
    "predicted_probability",
    "prob_up",
    "score",
    "confidence",
    "diagnostic_score",
    "y_score_or_probability",
}
BAR_ALIASES = {"open", "high", "low", "close", "volume", "o", "h", "l", "c", "v"}
CLAIM_BOUNDARY = {
    "local_repo_scan_only": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_model_update": True,
    "no_accuracy_claim": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Artifact discovery only; accuracy requires explicit local forecast-vs-actual rows."


def _has_parquet_engine() -> bool:
    try:
        import pyarrow  # noqa: F401

        return True
    except ImportError:
        try:
            import fastparquet  # noqa: F401

            return True
        except ImportError:
            return False


def _lower_fields(fields: list[str] | tuple[str, ...]) -> set[str]:
    return {str(field).strip().lower() for field in fields if str(field).strip()}


def _should_skip_dir(dirname: str) -> bool:
    lowered = dirname.lower()
    return lowered in EXCLUDED_DIR_NAMES or any(lowered.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _candidate_paths(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    walked_dirs = 0
    for dirpath, dirnames, filenames in os.walk(root):
        walked_dirs += 1
        current_path = Path(dirpath)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            depth = MAX_WALK_DEPTH + 1
        dirnames[:] = [dirname for dirname in dirnames if not _should_skip_dir(dirname)]
        if depth >= MAX_WALK_DEPTH:
            dirnames[:] = []
        if walked_dirs > MAX_WALK_DIRS:
            break
        for filename in filenames:
            path = Path(dirpath) / filename
            suffix = path.suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                continue
            lowered_name = path.name.lower()
            if not any(token in lowered_name for token in LIKELY_NAME_TOKENS):
                continue
            try:
                if path.stat().st_size > MAX_INSPECT_BYTES:
                    continue
            except OSError:
                continue
            paths.append(path)
            if len(paths) >= MAX_DISCOVERY_FILES:
                return tuple(sorted(dict.fromkeys(paths), key=lambda item: str(item)))
    return tuple(sorted(dict.fromkeys(paths), key=lambda item: str(item)))


def _csv_schema(path: Path) -> tuple[list[str], int | None, list[str]]:
    risk_notes: list[str] = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            count = 0
            for count, _ in enumerate(reader, start=1):
                if count >= 10_000:
                    risk_notes.append("row_count_estimate_capped")
                    break
            return fields, count, risk_notes
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return [], None, [f"csv_schema_error:{type(exc).__name__}"]


def _json_schema(path: Path) -> tuple[list[str], int | None, list[str]]:
    risk_notes: list[str] = []
    try:
        text = path.read_text(encoding="utf-8-sig")[:MAX_TEXT_SAMPLE_BYTES]
        payload = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [], None, [f"json_schema_error:{type(exc).__name__}"]
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if isinstance(rows, list):
        fields: set[str] = set()
        for row in rows[:50]:
            if isinstance(row, dict):
                fields.update(str(key) for key in row)
        return sorted(fields), len(rows), risk_notes
    if isinstance(payload, dict):
        return sorted(str(key) for key in payload), 1, risk_notes
    return [], None, ["json_payload_not_rows"]


def _jsonl_schema(path: Path) -> tuple[list[str], int | None, list[str]]:
    risk_notes: list[str] = []
    fields: set[str] = set()
    count = 0
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if not line.strip():
                    continue
                count += 1
                if count <= 50:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        fields.update(str(key) for key in row)
                    else:
                        risk_notes.append("jsonl_row_not_object")
                if count >= 10_000:
                    risk_notes.append("row_count_estimate_capped")
                    break
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [], None, [f"jsonl_schema_error:{type(exc).__name__}"]
    return sorted(fields), count, risk_notes


def _parquet_schema(path: Path) -> tuple[list[str], int | None, list[str]]:
    if not _has_parquet_engine():
        return [], None, ["parquet_engine_unavailable"]
    try:
        import pandas as pd

        frame = pd.read_parquet(path, columns=None)
        return [str(column) for column in frame.columns], int(len(frame)), []
    except Exception as exc:  # noqa: BLE001 - optional engine/schema probe only.
        return [], None, [f"parquet_schema_error:{type(exc).__name__}"]


def _inspect_schema(path: Path) -> tuple[list[str], int | None, list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _csv_schema(path)
    if suffix == ".json":
        return _json_schema(path)
    if suffix == ".jsonl":
        return _jsonl_schema(path)
    if suffix == ".parquet":
        return _parquet_schema(path)
    return [], None, ["unsupported_suffix"]


def _missing_columns(fields: set[str]) -> list[str]:
    required_groups = {
        "ticker_or_symbol": IDENTITY_ALIASES,
        "model_identifier": MODEL_ALIASES,
        "horizon": HORIZON_ALIASES,
        "forecast_timestamp": TIME_ALIASES,
        "forecast_value": FORECAST_ALIASES,
        "actual_value": ACTUAL_ALIASES,
    }
    return [name for name, aliases in required_groups.items() if fields.isdisjoint(aliases)]


def _classify_candidate(path: Path, repo_root: Path) -> dict[str, Any]:
    schema, row_count, risk_notes = _inspect_schema(path)
    fields = _lower_fields(schema)
    missing = _missing_columns(fields)
    has_forecast = not fields.isdisjoint(FORECAST_ALIASES)
    has_actual = not fields.isdisjoint(ACTUAL_ALIASES)
    has_identity = not fields.isdisjoint(IDENTITY_ALIASES)
    has_model = not fields.isdisjoint(MODEL_ALIASES)
    has_horizon = not fields.isdisjoint(HORIZON_ALIASES)
    has_time = not fields.isdisjoint(TIME_ALIASES)
    has_probability = not fields.isdisjoint(PROBABILITY_ALIASES)
    has_bars = len(fields.intersection(BAR_ALIASES)) >= 5
    usable_for_accuracy = has_forecast and has_actual and has_identity
    usable_for_tuning = usable_for_accuracy and has_model and has_horizon and has_time and has_probability
    if has_bars and not usable_for_accuracy:
        risk_notes.append("bar_data_only_not_forecast_actual")
    if not schema:
        risk_notes.append("schema_unavailable")
    if "secret" in path.name.lower() or "config" in path.name.lower():
        risk_notes.append("sensitive_name_skipped_from_claims")
    return {
        "path": _safe_relative(path, repo_root),
        "suffix": path.suffix.lower(),
        "schema_guess": schema,
        "row_count_estimate": row_count,
        "usable_for_accuracy": usable_for_accuracy,
        "usable_for_tuning": usable_for_tuning,
        "missing_columns": missing,
        "risk_notes": sorted(set(risk_notes)),
    }


def discover_forecast_actual_artifacts(*, repo_root: str = ".") -> dict:
    """Inspect safe local candidate files and classify forecast-vs-actual usability."""

    root = Path(repo_root).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"repo_root not found: {repo_root}")
    candidates = tuple(_classify_candidate(path, root) for path in _candidate_paths(root))
    usable_accuracy = [item for item in candidates if item["usable_for_accuracy"]]
    usable_tuning = [item for item in candidates if item["usable_for_tuning"]]
    return {
        "discovery_status": "completed",
        "repo_root": str(root),
        "candidate_file_count": len(candidates),
        "usable_accuracy_file_count": len(usable_accuracy),
        "usable_tuning_file_count": len(usable_tuning),
        "candidate_files": list(candidates),
        "ignored_directories": sorted(EXCLUDED_DIR_NAMES),
        "supported_file_types": list(SUPPORTED_SUFFIXES),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_actual_artifact_report(result: dict) -> str:
    """Render a compact discovery report."""

    lines = [
        "# Forecast-vs-Actual Artifact Discovery",
        "",
        f"Discovery status: {result.get('discovery_status')}",
        f"Candidate files: {result.get('candidate_file_count')}",
        f"Usable for accuracy: {result.get('usable_accuracy_file_count')}",
        f"Usable for tuning: {result.get('usable_tuning_file_count')}",
        "",
        "Candidates:",
    ]
    candidates = result.get("candidate_files") or []
    if not candidates:
        lines.append("- none")
    else:
        for item in candidates[:25]:
            lines.append(
                "- {path}: rows={rows}, accuracy={accuracy}, tuning={tuning}, missing={missing}".format(
                    path=item.get("path"),
                    rows=item.get("row_count_estimate"),
                    accuracy=item.get("usable_for_accuracy"),
                    tuning=item.get("usable_for_tuning"),
                    missing=",".join(item.get("missing_columns") or ["none"]),
                )
            )
        if len(candidates) > 25:
            lines.append(f"- additional candidates omitted from report: {len(candidates) - 25}")
    lines.extend(
        [
            "",
            "Boundary:",
            "Discovery does not compute accuracy, run tuning, or write files.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover local forecast-vs-actual candidate artifacts.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = discover_forecast_actual_artifacts(repo_root=args.repo_root)
    if args.format == "report":
        print(render_forecast_actual_artifact_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
