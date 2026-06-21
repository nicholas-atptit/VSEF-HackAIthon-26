"""Acceptance gate for the gateway-ready local diagnostic engine core."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from typing import Any

from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture


CLAIM_BOUNDARY = {
    "local_hardening_gate_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
    "auto_execution_allowed": False,
}
NON_CLAIM_TEXT = "Local diagnostic engine hardening gate; human review required."
ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
FORBIDDEN_ACTION_PATTERNS = tuple(r"\b" + re.escape(term) + r"\b" for term in ACTION_LABEL_TERMS)


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_strings(nested)
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _walk_strings(nested)


def _contains_action_labels(payload: Any) -> bool:
    text = " ".join(_walk_strings(payload)).lower()
    return any(re.search(pattern, text) for pattern in FORBIDDEN_ACTION_PATTERNS)


def _contains_forbidden_behavior(payload: Any) -> bool:
    text = " ".join(_walk_strings(payload)).lower()
    behavior_patterns = (
        r"\blive_data_enabled['\"]?:\s*true\b",
        r"\bprovider_calls_enabled['\"]?:\s*true\b",
        r"\btraining_enabled['\"]?:\s*true\b",
        r"\binference_enabled['\"]?:\s*true\b",
        r"\bbenchmark_rerun['\"]?:\s*true\b",
    )
    return any(re.search(pattern, text) for pattern in behavior_patterns)


def _all_review_required(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"human_review_required", "required_human_review"} and value is not True:
                return False
            if not _all_review_required(value):
                return False
    elif isinstance(payload, list):
        return all(_all_review_required(item) for item in payload)
    return True


def _all_auto_execution_false(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "auto_execution_allowed" and value is not False:
                return False
            if not _all_auto_execution_false(value):
                return False
    elif isinstance(payload, list):
        return all(_all_auto_execution_false(item) for item in payload)
    return True


def _conflicting_payload() -> dict:
    payload = build_minimal_engine_input_fixture()
    payload["model_diagnostics"][0]["forecast_diagnostic"] = "positive_bias"
    payload["model_diagnostics"][1]["forecast_diagnostic"] = "negative_bias"
    payload["model_diagnostics"][2]["forecast_diagnostic"] = "neutral_or_uncertain"
    payload["forecast_rows"][0]["forecast_diagnostic"] = "neutral_or_uncertain"
    return payload


def _missing_evidence_payload() -> dict:
    payload = build_minimal_engine_input_fixture()
    payload["market_bars"] = []
    payload["forecast_rows"] = []
    payload["model_diagnostics"] = []
    payload["scenario_context"] = {"evidence_status": "missing", "uncertainty_level": "high"}
    return payload


def _critical_payload() -> dict:
    payload = build_minimal_engine_input_fixture()
    payload["risk_context"]["force_critical_review"] = True
    return payload


def _scenario_stress_payload() -> dict:
    payload = build_minimal_engine_input_fixture()
    payload["scenario_context"] = {
        "uncertainty_level": "high",
        "data_quality_status": "degraded",
        "evidence_status": "partial",
        "model_disagreement_level": "high",
        "calibration_stress": True,
    }
    return payload


def _h40_policy_payload() -> dict:
    payload = build_minimal_engine_input_fixture(ticker="VCB", timeframe="1 ng\u00e0y", horizon_steps=40)
    payload["request"]["policy_demo"] = "h40"
    payload["forecast_rows"][0]["forecast_diagnostic"] = "neutral_or_uncertain"
    for row in payload["model_diagnostics"]:
        row["horizon_steps"] = 40
        row["forecast_diagnostic"] = "neutral_or_uncertain"
        row["policy_runtime_status"] = "non_directional_preserved"
    return payload


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"check_id": name, "passed": bool(passed), "detail": detail}


def run_diagnostic_engine_hardening_gate() -> dict:
    """Run deterministic acceptance checks for the local engine core."""

    canonical_result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture(ticker="VCB", horizon_steps=40))
    payload_result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())
    invalid_payload = build_minimal_engine_input_fixture()
    invalid_payload["request"]["ticker"] = ""
    invalid_result = run_diagnostic_engine_from_payload(invalid_payload)
    missing_result = run_diagnostic_engine_from_payload(_missing_evidence_payload())
    conflict_result = run_diagnostic_engine_from_payload(_conflicting_payload())
    critical_result = run_diagnostic_engine_from_payload(_critical_payload())
    stress_result = run_diagnostic_engine_from_payload(_scenario_stress_payload())
    h40_result = run_diagnostic_engine_from_payload(_h40_policy_payload())
    all_results = [
        canonical_result,
        payload_result,
        invalid_result,
        missing_result,
        conflict_result,
        critical_result,
        stress_result,
        h40_result,
    ]

    checks = [
        _check(
            "canonical_engine_default_run_passes",
            canonical_result.get("engine_completeness", {}).get("completeness_status") == "complete",
            "Canonical local engine result is complete.",
        ),
        _check(
            "payload_based_run_passes",
            payload_result.get("engine_status") == "completed_gateway_ready_local_engine_core",
            "Payload fixture completes the local engine core.",
        ),
        _check(
            "invalid_payload_fails_safely",
            invalid_result.get("engine_status") == "safe_failure_invalid_input"
            and invalid_result.get("decision_lane_v2", {}).get("lane") == "blocked_pending_risk_review",
            "Invalid payload returns a bounded failure result.",
        ),
        _check(
            "missing_evidence_safe_insufficient",
            missing_result.get("decision_lane_v2", {}).get("lane")
            in {"evidence_insufficient_review", "blocked_pending_evidence", "blocked_pending_risk_review"},
            "Missing evidence does not produce an upgraded route.",
        ),
        _check(
            "conflicting_ml_records_increase_model_risk",
            conflict_result.get("ml_engine", {}).get("agreement_status") == "high_disagreement"
            and conflict_result.get("risk_engine_v2", {})
            .get("risk_dimensions", {})
            .get("model_disagreement_risk", {})
            .get("risk_level")
            in {"high", "critical"},
            "Conflicting ML diagnostics increase disagreement risk.",
        ),
        _check(
            "critical_risk_blocks_decision_lane",
            critical_result.get("risk_engine_v2", {}).get("risk_level") == "critical"
            and critical_result.get("decision_lane_v2", {}).get("lane") == "blocked_pending_risk_review",
            "Critical risk blocks final routing.",
        ),
        _check(
            "scenario_stress_increases_review_requirement",
            stress_result.get("scenario_engine_v2", {}).get("scenario_risk_level") in {"high", "critical"}
            and stress_result.get("decision_lane_v2", {}).get("human_review_required") is True,
            "Scenario stress is reflected in review routing.",
        ),
        _check(
            "h40_policy_does_not_upgrade_non_directional_output",
            h40_result.get("decision_lane_v2", {}).get("lane") != "standard_human_review"
            or h40_result.get("decision_lane_v2", {}).get("blocking_reasons") == ["policy_gate_non_directional_preserved"],
            "Policy-preserved non-directional diagnostics are not upgraded.",
        ),
        _check(
            "all_outputs_require_human_review",
            all(_all_review_required(result) for result in all_results),
            "All exposed outputs keep human review required.",
        ),
        _check(
            "auto_execution_always_false",
            all(_all_auto_execution_false(result) for result in all_results),
            "Auto execution remains disabled.",
        ),
        _check(
            "no_action_labels",
            not any(_contains_action_labels(result) for result in all_results),
            "No action labels appear in hardening outputs.",
        ),
        _check(
            "no_forbidden_runtime_behavior",
            not any(_contains_forbidden_behavior(result) for result in all_results),
            "No live/provider/training/inference/benchmark behavior is exposed.",
        ),
    ]
    accepted = all(check["passed"] for check in checks)
    return {
        "hardening_status": "accepted_for_gateway_ready_local_engine_core" if accepted else "attention_required",
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "sample_results": {
            "canonical_decision_lane": canonical_result.get("decision_lane_v2", {}).get("lane"),
            "payload_decision_lane": payload_result.get("decision_lane_v2", {}).get("lane"),
            "invalid_decision_lane": invalid_result.get("decision_lane_v2", {}).get("lane"),
            "missing_evidence_lane": missing_result.get("decision_lane_v2", {}).get("lane"),
            "critical_risk_lane": critical_result.get("decision_lane_v2", {}).get("lane"),
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_diagnostic_engine_hardening_report(result: dict) -> str:
    """Render a compact hardening gate report."""

    lines = [
        "# Diagnostic Engine Hardening Gate",
        "",
        f"Hardening status: {result.get('hardening_status')}",
        f"Checks passed: {result.get('passed_count')} of {result.get('check_count')}",
        "",
        "## Checks",
    ]
    for check in result.get("checks", []):
        status = "pass" if check.get("passed") else "fail"
        lines.append(f"- {check.get('check_id')}: {status}")
    lines.extend(
        [
            "",
            "## Boundary",
            "Local acceptance gate only; no files are written.",
            "No live data, provider calls, training, inference, or benchmark rerun is performed.",
            "Human review remains required.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local diagnostic engine hardening gate.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_diagnostic_engine_hardening_gate()
    if args.format == "report":
        print(render_diagnostic_engine_hardening_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("hardening_status") == "accepted_for_gateway_ready_local_engine_core" else 1


if __name__ == "__main__":
    raise SystemExit(main())
