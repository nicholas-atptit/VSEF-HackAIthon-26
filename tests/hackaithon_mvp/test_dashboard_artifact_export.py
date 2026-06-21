import json
import subprocess
import sys

from src.hackaithon_mvp.dashboard_artifact_export import (
    build_dashboard_artifact,
    render_dashboard_artifact_json,
    validate_dashboard_artifact,
)


def test_dashboard_artifact_validates_without_built_web_dashboard():
    artifact = build_dashboard_artifact()
    validation = validate_dashboard_artifact(artifact)

    assert validation["is_valid"] is True
    assert artifact["artifact_type"] == "dashboard_ready_summary"
    assert artifact["generated_from"] == "local_static_demo"
    assert artifact["claim_boundary"]["dashboard_web_app_created"] is False
    assert artifact["claim_boundary"]["writes_files_by_default"] is False


def test_dashboard_artifact_json_round_trips():
    artifact = build_dashboard_artifact()
    rendered = render_dashboard_artifact_json(artifact)

    assert json.loads(rendered)["artifact_type"] == "dashboard_ready_summary"
    assert "forecast_diagnostic" in rendered


def test_dashboard_artifact_write_requires_explicit_path(tmp_path):
    output_path = tmp_path / "dashboard_artifact.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.dashboard_artifact_export",
            "--format",
            "json",
            "--write",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))["artifact_type"] == "dashboard_ready_summary"
    assert json.loads(completed.stdout)["artifact_type"] == "dashboard_ready_summary"


def test_dashboard_artifact_cli_default_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.dashboard_artifact_export"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout)["non_claim"]
