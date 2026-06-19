"""Catalog-backed registry for generated engine specs."""

from __future__ import annotations

import json
from pathlib import Path

from .engine_spec import EngineSpec


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_DIR = REPO_ROOT / "catalogs" / "hackaithon_mvp"
DEFAULT_CATALOG_FILES = (
    "baseline_engine_catalog.jsonl",
    "support_engine_catalog.jsonl",
    "stack_engine_catalog.jsonl",
)


class EngineNotFoundError(KeyError):
    """Raised when a requested engine ID is absent from generated catalogs."""


def load_engine_specs(catalog_dir: str | Path | None = None) -> tuple[EngineSpec, ...]:
    root = Path(catalog_dir) if catalog_dir is not None else DEFAULT_CATALOG_DIR
    specs: list[EngineSpec] = []
    for filename in DEFAULT_CATALOG_FILES:
        path = root / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    specs.append(EngineSpec.from_dict(json.loads(stripped)))
    return tuple(sorted(specs, key=lambda spec: spec.engine_id))


class EngineRegistry:
    """Lookup helper for generated engine catalogs."""

    def __init__(self, specs: tuple[EngineSpec, ...]):
        self._specs = specs
        self._by_id = {spec.engine_id: spec for spec in specs}
        if len(self._by_id) != len(specs):
            raise ValueError("duplicate engine_id found in catalogs")

    @classmethod
    def from_catalog_dir(cls, catalog_dir: str | Path | None = None) -> "EngineRegistry":
        return cls(load_engine_specs(catalog_dir))

    def get(self, engine_id: str) -> EngineSpec:
        try:
            return self._by_id[engine_id]
        except KeyError as exc:
            raise EngineNotFoundError(f"engine_id not found in generated catalogs: {engine_id}") from exc

    def list_specs(self) -> tuple[EngineSpec, ...]:
        return self._specs
