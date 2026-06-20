import json
import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.diagnostic_dag.dag_cli", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_show_dag_exits_cleanly():
    completed = _run("--show-dag")
    payload = json.loads(completed.stdout)

    assert payload["node_count"] == 13


def test_cli_validate_only_exits_cleanly():
    completed = _run("--validate-only")
    payload = json.loads(completed.stdout)

    assert payload["is_valid"] is True


def test_cli_normal_execution_exits_cleanly():
    completed = _run("--ticker", "VCB", "--timeframe", "1 ngày", "--horizon-steps", "1")
    payload = json.loads(completed.stdout)

    assert payload["dag_valid"] is True
    assert payload["ticker"] == "VCB"
    assert payload["timeframe"] == "1d"


def test_cli_policy_execution_exits_cleanly():
    completed = _run("--ticker", "VCB", "--timeframe", "1 ngày", "--horizon-steps", "1", "--policy-demo", "h40")
    payload = json.loads(completed.stdout)

    assert payload["dag_valid"] is True
    assert payload["final_state"]["policy_metadata"]["policy_id"] == "quant_core_policy.h40.eligible_slice_gate.v1"
