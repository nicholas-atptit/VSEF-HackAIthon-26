"""Read-only local cache discovery for offline gateway candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


CLAIM_BOUNDARY = {
    "local_cache_discovery_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local cache discovery for offline diagnostic inputs; read-only summary only."
DEFAULT_EXTENSIONS = (".csv", ".jsonl", ".json")
IGNORED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".pytest-tmp",
    "node_modules",
    "outputs",
    "artifacts",
    "reports",
    "tmp",
    "temp",
}


def _ignore_dir(path: Path, root: Path) -> bool:
    if path == root:
        return False
    name = path.name.lower()
    return name in IGNORED_DIRS or name.startswith(".tmp") or name.startswith(".") or name.startswith("tmp_")


def discover_local_cache_files(
    *,
    cache_root: str,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
) -> tuple[dict, ...]:
    """Discover local cache files by extension without loading file contents."""

    root = Path(cache_root).expanduser()
    if not root.exists() or not root.is_dir():
        return tuple()
    accepted = {extension.lower() for extension in extensions}
    candidates: list[dict[str, Any]] = []
    stack = [root]
    while stack:
        current = stack.pop()
        if _ignore_dir(current, root):
            continue
        for child in current.iterdir():
            if child.is_dir():
                if not _ignore_dir(child, root):
                    stack.append(child)
                continue
            suffix = child.suffix.lower()
            if suffix in accepted:
                candidates.append(
                    {
                        "path": str(child),
                        "extension": suffix,
                        "size_bytes": child.stat().st_size,
                        "large_file_summary_only": child.stat().st_size > 5_000_000,
                    }
                )
    return tuple(sorted(candidates, key=lambda row: row["path"]))


def build_local_cache_manifest(
    *,
    cache_root: str,
) -> dict:
    """Build a read-only local cache manifest."""

    root = Path(cache_root).expanduser()
    files = discover_local_cache_files(cache_root=cache_root)
    extension_counts = Counter(row["extension"] for row in files)
    warnings: list[str] = []
    if not root.exists():
        warnings.append("cache root does not exist")
    elif not root.is_dir():
        warnings.append("cache root is not a directory")
    if not files:
        warnings.append("no candidate local cache files discovered")
    return {
        "manifest_status": "completed" if root.exists() and root.is_dir() else "missing_cache_root",
        "cache_root": str(root),
        "file_count": len(files),
        "extension_counts": dict(sorted(extension_counts.items())),
        "candidate_datasets": files,
        "warnings": warnings,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def validate_local_cache_manifest(manifest: dict) -> dict:
    """Validate a local cache manifest shape and boundary flags."""

    errors: list[str] = []
    if not isinstance(manifest, dict):
        errors.append("manifest must be an object")
        manifest = {}
    for field in ("manifest_status", "cache_root", "file_count", "extension_counts", "candidate_datasets"):
        if field not in manifest:
            errors.append(f"missing manifest field: {field}")
    boundary = manifest.get("claim_boundary", {})
    for key, expected in CLAIM_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"claim_boundary.{key} must be {expected}")
    return {
        "is_valid": not errors,
        "errors": errors,
        "warnings": list(manifest.get("warnings", []) or []),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def run_local_cache_gateway_readiness(
    *,
    cache_root: str,
) -> dict:
    """Return a read-only readiness summary for local cache files."""

    manifest = build_local_cache_manifest(cache_root=cache_root)
    validation = validate_local_cache_manifest(manifest)
    return {
        "readiness_status": "ready_for_offline_gateway_candidates" if validation["is_valid"] else "attention_required",
        "manifest": manifest,
        "validation": validation,
        "file_count": manifest.get("file_count", 0),
        "extension_counts": manifest.get("extension_counts", {}),
        "candidate_datasets": manifest.get("candidate_datasets", ()),
        "warnings": list(manifest.get("warnings", []) or []),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_local_cache_gateway_report(result: dict) -> str:
    """Render a compact local cache readiness report."""

    lines = [
        "# Local Cache Gateway",
        "",
        f"Readiness status: {result.get('readiness_status')}",
        f"File count: {result.get('file_count')}",
        f"Extension counts: {json.dumps(result.get('extension_counts', {}), sort_keys=True)}",
        "",
        "## Candidate datasets",
    ]
    candidates = result.get("candidate_datasets", []) or []
    if not candidates:
        lines.append("- none")
    else:
        for row in candidates[:20]:
            lines.append(f"- {row.get('path')} ({row.get('extension')}, {row.get('size_bytes')} bytes)")
    if result.get("warnings"):
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in result["warnings"]]])
    lines.extend(
        [
            "",
            "## Boundary",
            "Read-only local cache discovery only; files are summarized, not loaded for processing.",
            "No live data, provider calls, training, inference, or benchmark rerun is performed.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect local cache files for offline gateway candidates.")
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_local_cache_gateway_readiness(cache_root=args.cache_root)
    if args.format == "report":
        print(render_local_cache_gateway_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("readiness_status") == "ready_for_offline_gateway_candidates" else 1


if __name__ == "__main__":
    raise SystemExit(main())
