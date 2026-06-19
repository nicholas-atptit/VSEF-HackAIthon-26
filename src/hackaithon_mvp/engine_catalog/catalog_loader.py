"""Load generated engine catalogs."""

from __future__ import annotations

import json
from pathlib import Path

from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec

from .catalog_schema import DEFAULT_CATALOG_DIR


def load_catalog(path: str | Path) -> tuple[EngineSpec, ...]:
    specs: list[EngineSpec] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                specs.append(EngineSpec.from_dict(json.loads(stripped)))
    return tuple(sorted(specs, key=lambda spec: spec.engine_id))


def load_catalogs(catalog_dir: str | Path | None = None) -> tuple[EngineSpec, ...]:
    root = Path(catalog_dir) if catalog_dir is not None else DEFAULT_CATALOG_DIR
    specs: list[EngineSpec] = []
    for name in ("baseline_engine_catalog.jsonl", "support_engine_catalog.jsonl", "stack_engine_catalog.jsonl"):
        path = root / name
        if path.exists():
            specs.extend(load_catalog(path))
    return tuple(sorted(specs, key=lambda spec: spec.engine_id))
