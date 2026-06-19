"""Write generated engine catalogs and summaries."""

from __future__ import annotations

from pathlib import Path

from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec

from .baseline_catalog_generator import generate_baseline_catalog
from .catalog_schema import DEFAULT_CATALOG_DIR, spec_to_json_line
from .stack_catalog_generator import generate_stack_catalog
from .support_catalog_generator import generate_support_catalog


def write_jsonl(path: Path, specs: tuple[EngineSpec, ...]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for spec in specs:
            handle.write(spec_to_json_line(spec))
            handle.write("\n")
    return path


def write_summary(path: Path, title: str, specs: tuple[EngineSpec, ...], notes: tuple[str, ...]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_type: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for spec in specs:
        by_type[spec.engine_type] = by_type.get(spec.engine_type, 0) + 1
        family = spec.model_family or "none"
        by_family[family] = by_family.get(family, 0) + 1

    lines = [
        f"# {title}",
        "",
        f"Generated engine count: {len(specs)}",
        "",
        "## By Engine Type",
        "",
        *[f"- `{key}`: {value}" for key, value in sorted(by_type.items())],
        "",
        "## By Model Family",
        "",
        *[f"- `{key}`: {value}" for key, value in sorted(by_family.items())],
        "",
        "## Notes",
        "",
        *[f"- {note}" for note in notes],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_all_catalogs(catalog_dir: str | Path | None = None) -> dict[str, int]:
    root = Path(catalog_dir) if catalog_dir is not None else DEFAULT_CATALOG_DIR
    baseline = generate_baseline_catalog()
    support = generate_support_catalog()
    stack = generate_stack_catalog()

    write_jsonl(root / "baseline_engine_catalog.jsonl", baseline)
    write_jsonl(root / "support_engine_catalog.jsonl", support)
    write_jsonl(root / "stack_engine_catalog.jsonl", stack)
    write_summary(
        root / "baseline_engine_catalog_summary.md",
        "Baseline Engine Catalog Summary",
        baseline,
        (
            "Generated from in-scope metadata adapters.",
            "Each baseline engine can run independently in static evidence mode when matching local evidence exists.",
            "No provider access, model training, inference, or benchmark rerun is performed.",
        ),
    )
    write_summary(
        root / "support_engine_catalog_summary.md",
        "Support Engine Catalog Summary",
        support,
        (
            "Support engines consume dependency outputs and skip safely when outputs are unavailable.",
            "Generated across support type, universe, target, horizon, feature scope, and model family.",
            "Out-of-scope model families and provider access are not included.",
        ),
    )
    write_summary(
        root / "stack_engine_catalog_summary.md",
        "Stack Engine Catalog Summary",
        stack,
        (
            "Stack engines are governed static MVP combiners over dependency outputs.",
            "Generated across stack type, target, horizon, feature set, and selection policy.",
            "No training, relocking, or benchmark rerun is performed.",
        ),
    )
    return {"baseline": len(baseline), "support": len(support), "stack": len(stack)}


if __name__ == "__main__":
    counts = write_all_catalogs()
    print(counts)
