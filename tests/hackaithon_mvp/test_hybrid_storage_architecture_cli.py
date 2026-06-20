import json
import subprocess
import sys


def _run_cli(section: str | None = None) -> dict:
    command = [sys.executable, "-m", "src.hackaithon_mvp.hybrid_storage_architecture"]
    if section is not None:
        command.extend(["--section", section])
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_hybrid_storage_cli_default_outputs_architecture():
    output = _run_cli()

    assert output["architecture_name"] == "hybrid_storage_architecture"
    assert output["recommended_current"] == "local_partitioned_file_adapter"


def test_hybrid_storage_cli_exits_cleanly_for_all_sections():
    architecture = _run_cli("architecture")
    component_map = _run_cli("component-map")
    options = _run_cli("options")
    all_sections = _run_cli("all")

    assert architecture["layers"]
    assert component_map["mappings"]["diagnostic_dag_runtime"] == ["dag_runs", "audit_log"]
    assert "hybrid_target" in options["options"]
    assert set(all_sections) == {"architecture", "component_map", "options"}
