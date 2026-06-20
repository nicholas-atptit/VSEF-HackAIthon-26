import json
import subprocess
from pathlib import Path

from src.hackaithon_mvp.engine_catalog.catalog_loader import load_catalog

ROOT = Path("catalogs/hackaithon_mvp")


def test_catalog_generation_manifest_records_full_counts_and_scope():
    manifest = json.loads((ROOT / "catalog_generation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["baseline_engine_count"] == 32850
    assert manifest["support_engine_count"] == 22500
    assert manifest["stack_engine_count"] == 22500
    assert manifest["catalogs_are_generated_artifacts"] is True
    assert manifest["full_jsonl_catalogs_are_not_tracked"] is True
    assert manifest["qml_excluded"] is True
    assert manifest["data_gateway_excluded"] is True


def test_tracked_sample_catalogs_are_small_and_valid():
    sample_paths = sorted((ROOT / "samples").glob("*_sample.jsonl"))
    assert {path.name for path in sample_paths} == {
        "baseline_engine_catalog_sample.jsonl",
        "support_engine_catalog_sample.jsonl",
        "stack_engine_catalog_sample.jsonl",
    }
    for path in sample_paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert 1 <= len(lines) <= 50
        specs = load_catalog(path)
        assert len(specs) == len(lines)
        assert all("qml" not in spec.engine_id.lower() for spec in specs)
        assert all("quantum" not in spec.engine_id.lower() for spec in specs)


def test_full_generated_jsonl_catalogs_are_not_required_in_git_snapshot():
    for path in (
        ROOT / "baseline_engine_catalog.jsonl",
        ROOT / "support_engine_catalog.jsonl",
        ROOT / "stack_engine_catalog.jsonl",
    ):
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            capture_output=True,
            text=True,
        )
        assert completed.returncode != 0
