import subprocess
import sys

from src.hackaithon_mvp.local_cache_gateway import (
    build_local_cache_manifest,
    discover_local_cache_files,
    run_local_cache_gateway_readiness,
    validate_local_cache_manifest,
)


def test_local_cache_gateway_discovers_files_and_ignores_generated_temp_dirs(tmp_path):
    (tmp_path / "bars.csv").write_text("ticker,timestamp,open,high,low,close,volume\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "bars.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / ".tmp_generated").mkdir()
    (tmp_path / ".tmp_generated" / "ignored.csv").write_text("ignored", encoding="utf-8")

    files = discover_local_cache_files(cache_root=str(tmp_path))
    paths = [row["path"] for row in files]

    assert len(files) == 2
    assert any(path.endswith("bars.csv") for path in paths)
    assert any(path.endswith("bars.jsonl") for path in paths)
    assert all("ignored.csv" not in path for path in paths)


def test_local_cache_manifest_validates_and_summarizes_extensions(tmp_path):
    (tmp_path / "bars.csv").write_text("", encoding="utf-8")
    (tmp_path / "records.json").write_text("[]", encoding="utf-8")

    manifest = build_local_cache_manifest(cache_root=str(tmp_path))
    validation = validate_local_cache_manifest(manifest)

    assert manifest["manifest_status"] == "completed"
    assert manifest["file_count"] == 2
    assert manifest["extension_counts"][".csv"] == 1
    assert manifest["extension_counts"][".json"] == 1
    assert validation["is_valid"] is True


def test_local_cache_gateway_readiness_handles_missing_root(tmp_path):
    result = run_local_cache_gateway_readiness(cache_root=str(tmp_path / "missing"))

    assert result["readiness_status"] == "ready_for_offline_gateway_candidates"
    assert "cache root does not exist" in result["warnings"]


def test_local_cache_gateway_cli_report_exits_cleanly(tmp_path):
    (tmp_path / "bars.csv").write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.local_cache_gateway",
            "--cache-root",
            str(tmp_path),
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Local Cache Gateway" in completed.stdout
    assert "Readiness status:" in completed.stdout
