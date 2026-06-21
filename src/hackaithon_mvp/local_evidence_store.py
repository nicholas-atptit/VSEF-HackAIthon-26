"""Explicit local JSONL store for LLM-readable diagnostic evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.llm_storage_contract import (
    CLAIM_BOUNDARY,
    NON_CLAIM_TEXT,
    validate_llm_readable_record,
)


RECORDS_FILE_NAME = "llm_readable_records.jsonl"


def _records_path(store_root: str) -> Path:
    return Path(store_root).expanduser() / RECORDS_FILE_NAME


def _record_text(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, default=str).lower()


def validate_evidence_store_root(store_root: str) -> dict:
    """Validate an explicit local store root without creating files."""

    errors: list[str] = []
    if not isinstance(store_root, str) or not store_root.strip():
        errors.append("store_root must be an explicit local path")
        path = None
    else:
        path = Path(store_root).expanduser()
        if path.exists() and not path.is_dir():
            errors.append("store_root must be a directory path")
    record_file = path / RECORDS_FILE_NAME if path is not None else None
    return {
        "is_valid": not errors,
        "explicit_store_root": path is not None,
        "store_root": str(path) if path is not None else None,
        "store_exists": bool(path.exists()) if path is not None else False,
        "record_file": str(record_file) if record_file is not None else None,
        "record_file_exists": bool(record_file.exists()) if record_file is not None else False,
        "jsonl_only": True,
        "errors": errors,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def write_llm_readable_records(
    *,
    records: tuple[dict, ...],
    store_root: str,
) -> dict:
    """Write validated records to an explicit local JSONL store."""

    root_validation = validate_evidence_store_root(store_root)
    if not root_validation["is_valid"]:
        return {
            "write_status": "refused_invalid_store_root",
            "record_count": 0,
            "written_count": 0,
            "store_root": root_validation.get("store_root"),
            "record_file": root_validation.get("record_file"),
            "errors": list(root_validation["errors"]),
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
    if not isinstance(records, tuple):
        return {
            "write_status": "refused_invalid_records",
            "record_count": 0,
            "written_count": 0,
            "store_root": root_validation.get("store_root"),
            "record_file": root_validation.get("record_file"),
            "errors": ["records must be a tuple"],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    normalized_records: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, record in enumerate(records):
        validation = validate_llm_readable_record(record)
        if validation["is_valid"]:
            normalized_records.append(validation["normalized_record"])
        else:
            errors.extend(f"records[{index}]: {error}" for error in validation["errors"])
    if errors:
        return {
            "write_status": "refused_invalid_records",
            "record_count": len(records),
            "written_count": 0,
            "store_root": root_validation.get("store_root"),
            "record_file": root_validation.get("record_file"),
            "errors": errors,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    store_path = Path(str(root_validation["store_root"]))
    store_path.mkdir(parents=True, exist_ok=True)
    record_file = _records_path(str(store_path))
    with record_file.open("w", encoding="utf-8") as handle:
        for record in normalized_records:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    return {
        "write_status": "written_local_jsonl",
        "record_count": len(records),
        "written_count": len(normalized_records),
        "store_root": str(store_path),
        "record_file": str(record_file),
        "jsonl_only": True,
        "read_only_for_llm": True,
        "errors": [],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def read_llm_readable_records(
    *,
    store_root: str,
    record_type: str | None = None,
) -> tuple[dict, ...]:
    """Read valid local evidence records from a JSONL store."""

    root_validation = validate_evidence_store_root(store_root)
    record_file_value = root_validation.get("record_file")
    if not root_validation["is_valid"] or not record_file_value:
        return tuple()
    record_file = Path(str(record_file_value))
    if not record_file.exists():
        return tuple()

    records: list[dict[str, Any]] = []
    with record_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            validation = validate_llm_readable_record(record)
            if not validation["is_valid"]:
                continue
            normalized = validation["normalized_record"]
            if record_type is None or normalized.get("record_type") == record_type:
                records.append(normalized)
    return tuple(records)


def search_llm_readable_records(
    *,
    store_root: str,
    query: str,
    record_type: str | None = None,
    limit: int = 5,
) -> tuple[dict, ...]:
    """Run simple keyword search over local JSONL evidence records."""

    records = read_llm_readable_records(store_root=store_root, record_type=record_type)
    bounded_limit = max(0, int(limit))
    if bounded_limit == 0:
        return tuple()
    tokens = [token for token in str(query or "").lower().split() if token]
    if not tokens:
        return tuple(records[:bounded_limit])

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for record in records:
        text = _record_text(record)
        score = sum(text.count(token) for token in tokens)
        if score > 0:
            scored.append((score, str(record.get("record_id", "")), record))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(record for _, _, record in scored[:bounded_limit])


def _demo_records() -> tuple[dict, ...]:
    from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
    from src.hackaithon_mvp.diagnostic_to_llm_records import build_llm_records_from_diagnostic_result
    from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture

    result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())
    return build_llm_records_from_diagnostic_result(result)


def render_store_write_report(result: dict) -> str:
    """Render a compact local evidence-store write report."""

    lines = [
        "# Local Evidence Store",
        "",
        f"Write status: {result.get('write_status')}",
        f"Records written: {result.get('written_count')} of {result.get('record_count')}",
        f"Store root: {result.get('store_root')}",
        f"Record file: {result.get('record_file')}",
        "JSONL only: True",
        "Read-only for LLM: True",
        "",
        "Boundary: explicit local writes only; no server database or vector database is created.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    if result.get("errors"):
        lines.extend(["", "Errors:", *[f"- {error}" for error in result["errors"]]])
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read or write the local LLM-readable evidence store.")
    parser.add_argument("--demo-write", action="store_true")
    parser.add_argument("--store-root", default="")
    parser.add_argument("--record-type", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.demo_write:
        result = write_llm_readable_records(records=_demo_records(), store_root=args.store_root)
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True, default=str))
        else:
            print(render_store_write_report(result), end="")
        return 0 if result.get("write_status") == "written_local_jsonl" else 1

    records = read_llm_readable_records(store_root=args.store_root, record_type=args.record_type)
    result = {
        "read_status": "records_available" if records else "no_records_available",
        "record_count": len(records),
        "records": records,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
