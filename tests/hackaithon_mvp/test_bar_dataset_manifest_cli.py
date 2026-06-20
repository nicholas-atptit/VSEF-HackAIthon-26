import json
import re
import subprocess
import sys


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bclient relationship\b",
)


def _assert_neutral(text: str) -> None:
    lowered = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_bar_dataset_manifest_cli_outputs_manifest_without_writing_by_default(tmp_path):
    dataset_root = tmp_path / "market_bars"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.bar_dataset_manifest",
            "--dataset-root",
            str(dataset_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["tickers_count"] == 30
    assert output["timeframes_count"] == 18
    assert output["database_created"] is False
    assert not dataset_root.exists()
    _assert_neutral(completed.stdout)


def test_bar_dataset_manifest_cli_write_flag_writes_only_requested_path(tmp_path):
    output_path = tmp_path / "outputs" / "bar_dataset_manifest.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.bar_dataset_manifest",
            "--dataset-root",
            "data/market_bars",
            "--write",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stdout_payload = json.loads(completed.stdout)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert stdout_payload["storage_design"]["canonical_data_format"] == "parquet"
    assert file_payload["storage_design"]["planned_query_adapter"] == "duckdb_compatible"
    assert list(tmp_path.rglob("bar_dataset_manifest.json")) == [output_path]
    _assert_neutral(completed.stdout)
