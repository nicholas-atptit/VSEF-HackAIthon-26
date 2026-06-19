"""Small JSON output store for static MVP engine runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .engine_result import EngineResult


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_ROOT = REPO_ROOT / "outputs" / "hackaithon_mvp" / "runs"


class EngineOutputStore:
    """Write run manifests and JSONL engine results without large artifacts."""

    def __init__(self, run_id: str, root_dir: str | Path | None = None):
        self.run_id = run_id
        self.root_dir = Path(root_dir) if root_dir is not None else DEFAULT_RUN_ROOT
        self.run_dir = self.root_dir / run_id

    def write_manifest(self, metadata: dict[str, Any] | None = None) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": self.run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "run_mode": "static_evidence_mvp",
            "metadata": metadata or {},
        }
        path = self.run_dir / "run_manifest.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    def append_result(self, result: EngineResult) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / "engine_results.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, sort_keys=True)
            handle.write("\n")
        return path
