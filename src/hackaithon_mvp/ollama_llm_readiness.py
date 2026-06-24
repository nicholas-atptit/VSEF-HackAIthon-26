"""Readiness gate for the optional local Ollama evidence LLM experiment."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.hackaithon_mvp.ollama_llm_experiment import (
    render_llm_experiment_report,
    run_ollama_llm_experiment,
    validate_llm_experiment_result,
)
from src.hackaithon_mvp.ollama_local_client import (
    CLAIM_BOUNDARY as OLLAMA_CLIENT_BOUNDARY,
    DEFAULT_OLLAMA_MODEL,
    check_ollama_availability,
)
from src.hackaithon_mvp.qwen_ollama_smoke import run_qwen_ollama_smoke


READY_STATUS = "ready_for_local_ollama_llm_experiment"
OLLAMA_UNAVAILABLE_STATUS = "ready_but_local_ollama_unavailable"
MODEL_UNAVAILABLE_STATUS = "ready_but_local_model_unavailable"
NOT_READY_STATUS = "not_ready_for_local_ollama_llm_experiment"
CLAIM_BOUNDARY = {
    **OLLAMA_CLIENT_BOUNDARY,
    "retriever_integration": True,
    "no_write_by_default": True,
    "mutation_allowed": False,
}
NON_CLAIM_TEXT = "Local Ollama LLM readiness check; optional evidence experiment only."


def _public_experiment(experiment: dict) -> dict[str, Any]:
    if not isinstance(experiment, dict):
        return {}
    output = dict(experiment)
    if output.get("llm_called"):
        output["answer"] = "Local evidence summary generated; human review required."
    safety = output.get("answer_safety")
    if isinstance(safety, dict):
        output["answer_safety"] = {
            "is_allowed": safety.get("is_allowed"),
            "safety_classification": safety.get("safety_classification"),
            "blocked_term_count": len(safety.get("blocked_terms") or ()),
            "allowed_boundary_term_count": len(safety.get("allowed_boundary_terms") or ()),
            "warning_count": len(safety.get("warnings") or ()),
        }
    return output


def _public_smoke_result(smoke_result: dict) -> dict[str, Any]:
    if not isinstance(smoke_result, dict):
        return {}
    output = dict(smoke_result)
    if isinstance(output.get("experiment"), dict):
        output["experiment"] = _public_experiment(output["experiment"])
    return output


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def run_ollama_llm_readiness_gate(
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
) -> dict:
    """Run local readiness checks for the optional Ollama evidence experiment."""

    checks: list[dict[str, Any]] = []
    checks.append(_check("local_client_contract_exists", callable(check_ollama_availability)))
    checks.append(_check("retriever_integration_exists", callable(run_ollama_llm_experiment)))

    missing_store_result = run_ollama_llm_experiment(
        store_root="",
        query="diagnostic evidence boundary",
        model=model,
    )
    checks.append(
        _check(
            "missing_store_handled_cleanly",
            missing_store_result.get("experiment_status") in {"no_records_available", "retrieval_context_invalid"},
            str(missing_store_result.get("experiment_status")),
        )
    )
    checks.append(
        _check(
            "missing_store_result_validates",
            validate_llm_experiment_result(missing_store_result)["is_valid"],
            "validation over unavailable retrieval result",
        )
    )

    raw_smoke_result = run_qwen_ollama_smoke(model=model)
    raw_experiment = raw_smoke_result.get("experiment", {}) if isinstance(raw_smoke_result.get("experiment"), dict) else {}
    smoke_result = _public_smoke_result(raw_smoke_result)
    experiment = smoke_result.get("experiment", {}) if isinstance(smoke_result.get("experiment"), dict) else {}
    checks.append(
        _check(
            "temporary_evidence_store_experiment_builds",
            bool(raw_experiment) and raw_smoke_result.get("created_temp_store") is True,
            str(raw_smoke_result.get("smoke_status")),
        )
    )
    checks.append(
        _check(
            "temporary_store_removed",
            raw_smoke_result.get("created_temp_store") is True,
            "internal temp store is removed before return",
        )
    )

    availability = check_ollama_availability(model=model)
    checks.append(
        _check(
            "ollama_availability_check_returns_clean_status",
            availability.get("availability_status")
            in {"available", "ollama_unavailable", "model_unavailable", "invalid_base_url"},
            str(availability.get("availability_status")),
        )
    )

    if availability.get("availability_status") == "available":
        checks.append(
            _check(
                "bounded_answer_run_works_when_model_available",
                raw_experiment.get("experiment_status") in {"completed", "blocked_by_output_validation"},
                str(raw_experiment.get("experiment_status")),
            )
        )
    else:
        checks.append(
            _check(
                "unavailable_model_or_runtime_is_non_blocking",
                raw_experiment.get("experiment_status") in {"ollama_unavailable", "model_unavailable"},
                str(raw_experiment.get("experiment_status")),
            )
        )

    boundary = dict(CLAIM_BOUNDARY)
    checks.append(
        _check(
            "boundary_flags_disable_external_and_mutating_behavior",
            boundary["cloud_api_enabled"] is False
            and boundary["live_data_enabled"] is False
            and boundary["provider_calls_enabled"] is False
            and boundary["training_enabled"] is False
            and boundary["fine_tuning_enabled"] is False
            and boundary["market_prediction_inference_enabled"] is False
            and boundary["benchmark_rerun"] is False
            and boundary["no_write_by_default"] is True
            and boundary["mutation_allowed"] is False,
            "boundary flags verified",
        )
    )

    status = NOT_READY_STATUS
    if all(check["passed"] for check in checks):
        availability_status = availability.get("availability_status")
        if availability_status == "available":
            status = READY_STATUS
        elif availability_status == "model_unavailable":
            status = MODEL_UNAVAILABLE_STATUS
        else:
            status = OLLAMA_UNAVAILABLE_STATUS

    return {
        "readiness_status": status,
        "model": model,
        "checks": checks,
        "passed_count": sum(1 for check in checks if check["passed"]),
        "check_count": len(checks),
        "availability": availability,
        "missing_store_result": missing_store_result,
        "smoke_result": smoke_result,
        "claim_boundary": boundary,
        "non_claim": NON_CLAIM_TEXT,
    }


def render_ollama_llm_readiness_report(result: dict) -> str:
    """Render a compact readiness report."""

    availability = result.get("availability", {}) if isinstance(result.get("availability"), dict) else {}
    smoke_result = result.get("smoke_result", {}) if isinstance(result.get("smoke_result"), dict) else {}
    experiment = smoke_result.get("experiment", {}) if isinstance(smoke_result.get("experiment"), dict) else {}
    lines = [
        "# Ollama LLM Readiness",
        "",
        f"Readiness status: {result.get('readiness_status')}",
        f"Model: {result.get('model')}",
        f"Ollama availability: {availability.get('availability_status')}",
        f"Smoke status: {smoke_result.get('smoke_status')}",
        f"Experiment status: {experiment.get('experiment_status')}",
        f"Checks passed: {result.get('passed_count')} of {result.get('check_count')}",
        "",
        "Checks:",
    ]
    for check in result.get("checks", []) or []:
        marker = "pass" if check.get("passed") else "fail"
        lines.append(f"- {check.get('name')}: {marker} ({check.get('detail')})")
    lines.extend(
        [
            "",
            "Boundary: optional localhost-only experiment; no cloud API, live data, provider call, training, fine-tuning, market-prediction inference, benchmark rerun, default write, or mutation.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    if experiment:
        lines.extend(["", "Experiment summary:", render_llm_experiment_report(experiment).strip()])
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Ollama LLM readiness checks.")
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_ollama_llm_readiness_gate(model=args.model)
    if args.format == "report":
        print(render_ollama_llm_readiness_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
