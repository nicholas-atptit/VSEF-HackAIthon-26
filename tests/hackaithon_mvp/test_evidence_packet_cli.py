import json
import subprocess
import sys


def test_evidence_packet_cli_prints_json_and_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.evidence_packet",
            "--ticker",
            "VCB",
            "--sample-size",
            "20",
            "--timeframe",
            "1 ngày",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["ticker"] == "VCB"
    assert output["timeframe"] == "1d"
    assert output["timeframe_unit"] == "day"
    assert output["human_review_required"] is True


def test_evidence_packet_cli_write_flag_writes_requested_path(tmp_path):
    output_path = tmp_path / "packets" / "latest_packet.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.evidence_packet",
            "--ticker",
            "VCB",
            "--sample-size",
            "20",
            "--timeframe",
            "1 ngày",
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
    assert stdout_payload["timeframe"] == "1d"
    assert file_payload["timeframe"] == "1d"
    assert list(tmp_path.rglob("*_packet.json")) == [output_path]
