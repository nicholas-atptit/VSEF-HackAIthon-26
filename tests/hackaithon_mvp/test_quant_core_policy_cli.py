import json
import subprocess
import sys


def _run_module(*args):
    return subprocess.run(
        [sys.executable, "-m", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_policy_registry_cli_exits_cleanly():
    listed = _run_module("src.hackaithon_mvp.quant_core_policy_registry", "--list-demo")
    shown_pva = _run_module("src.hackaithon_mvp.quant_core_policy_registry", "--show-demo", "predicted_vs_actual")
    shown_h40 = _run_module("src.hackaithon_mvp.quant_core_policy_registry", "--show-demo", "h40")

    assert json.loads(listed.stdout)["demo_policies"] == ["h40", "predicted_vs_actual"]
    assert json.loads(shown_pva.stdout)["policy_id"] == "quant_core_policy.pva.eligible_slice_gate.v1"
    assert json.loads(shown_h40.stdout)["policy_id"] == "quant_core_policy.h40.eligible_slice_gate.v1"


def test_policy_runtime_cli_exits_cleanly():
    pva = _run_module("src.hackaithon_mvp.quant_core_policy_runtime", "--demo", "predicted_vs_actual")
    h40 = _run_module("src.hackaithon_mvp.quant_core_policy_runtime", "--demo", "h40")

    assert json.loads(pva.stdout)["runtime_output"]["policy_runtime_status"] == "directional_allowed"
    assert json.loads(h40.stdout)["runtime_output"]["policy_runtime_status"] == "directional_allowed"
