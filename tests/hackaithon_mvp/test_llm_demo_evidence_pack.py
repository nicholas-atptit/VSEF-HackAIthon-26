import json
import subprocess
import sys

from src.hackaithon_mvp.llm_demo_evidence_pack import (
    build_rich_llm_demo_records,
    render_rich_llm_demo_pack_report,
    write_rich_llm_demo_store,
)
from src.hackaithon_mvp.local_evidence_store import read_llm_readable_records
from src.hackaithon_mvp.llm_storage_contract import validate_llm_readable_record


def test_rich_llm_demo_records_are_valid_and_cover_required_topics():
    records = build_rich_llm_demo_records()
    record_ids = {record["record_id"] for record in records}

    assert record_ids == {
        "architecture:scope_boundary",
        "engine-universe-sweep:full-summary",
        "diagnostic-engine:gateway-ready-core",
        "offline-gateway:v0",
        "risk-engine:v3",
        "fine-tune:control-plane",
        "llm:ollama-local-boundary",
    }
    assert all(validate_llm_readable_record(record)["is_valid"] for record in records)


def test_rich_llm_demo_records_include_latest_sweep_facts():
    records = {record["record_id"]: record for record in build_rich_llm_demo_records()}
    content = records["engine-universe-sweep:full-summary"]["content"]

    assert content["total_discovered"] == 77_850
    assert content["total_attempted"] == 77_850
    assert content["completed"] == 120
    assert content["skipped"] == 77_730
    assert content["failed"] == 0
    assert content["evidence_coverage_ratio"] == 0.001541


def test_rich_llm_demo_store_writes_only_with_explicit_store_root(tmp_path):
    result = write_rich_llm_demo_store(store_root=str(tmp_path))
    records = read_llm_readable_records(store_root=str(tmp_path))

    assert result["pack_status"] == "written"
    assert result["write_result"]["write_status"] == "written_local_jsonl"
    assert len(records) == 7


def test_rich_llm_demo_pack_report_renders_boundary(tmp_path):
    result = write_rich_llm_demo_store(store_root=str(tmp_path))
    report = render_rich_llm_demo_pack_report(result)

    assert "Rich LLM Demo Evidence Pack" in report
    assert "Writes require an explicit local store root" in report


def test_rich_llm_demo_pack_cli_no_write_by_default(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.llm_demo_evidence_pack"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["pack_status"] == "records_built"
    assert not (tmp_path / "llm_readable_records.jsonl").exists()


def test_rich_llm_demo_pack_cli_explicit_write(tmp_path):
    store_root = tmp_path / "store"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.llm_demo_evidence_pack",
            "--write-store",
            str(store_root),
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Pack status: written" in completed.stdout
    assert (store_root / "llm_readable_records.jsonl").exists()
