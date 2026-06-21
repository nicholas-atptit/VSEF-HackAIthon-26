"""Readiness gate for offline gateway, local harness, Risk V3, and fine-tune controls."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.dag_backtest_harness import build_dag_backtest_fixture, run_dag_backtest_from_payloads
from src.hackaithon_mvp.fine_tune_control_plane import (
    assess_fine_tune_readiness,
    build_fine_tune_experiment_candidate,
    validate_fine_tune_candidate,
)
from src.hackaithon_mvp.local_evidence_store import read_llm_readable_records
from src.hackaithon_mvp.offline_data_gateway import (
    CLAIM_BOUNDARY as GATEWAY_CLAIM_BOUNDARY,
    build_payload_from_local_records,
    run_offline_gateway_to_engine,
)
from src.hackaithon_mvp.risk_engine_v3 import run_risk_engine_v3


CLAIM_BOUNDARY = {
    **GATEWAY_CLAIM_BOUNDARY,
    "gateway_backtest_readiness_only": True,
    "fine_tune_candidate_only": True,
    "auto_training_allowed": False,
    "auto_execution_allowed": False,
}
NON_CLAIM_TEXT = "Readiness gate for offline diagnostic inputs, local harness checks, Risk V3, and fine-tune candidates."
ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
RELATIONSHIP_TERMS = (
    "".join(("corpor", "ate")),
    "".join(("spon", "sor")),
    "".join(("spon", "sorship")),
    "".join(("sup", "port")),
    "".join(("sup", "ported")),
    "".join(("sup", "ports")),
    "".join(("sup", "porting")),
    "".join(("fund", "ing")),
    "".join(("part", "nership")),
    "".join(("endorse", "ment")),
    "".join(("deploy", "ment")),
    "".join(("appro", "val")),
    "".join(("client ", "relationship")),
)
SCOPE_TERMS = ("".join(("q", "ml")), "".join(("non-", "q", "ml")), "".join(("non", "q", "ml")))
ADVISORY_TERMS = (" ".join(("financial", "advice")),)
FORBIDDEN_PATTERNS = tuple(
    r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
    for term in (*ACTION_LABEL_TERMS, *RELATIONSHIP_TERMS, *SCOPE_TERMS, *ADVISORY_TERMS)
)


def _fixture_rows() -> tuple[dict, ...]:
    return (
        {"ticker": "DEMO", "timestamp": "2026-01-01", "open": 100, "high": 105, "low": 99, "close": 102, "volume": 100000},
        {"ticker": "DEMO", "timestamp": "2026-01-02", "open": 102, "high": 106, "low": 101, "close": 104, "volume": 120000},
        {"ticker": "DEMO", "timestamp": "2026-01-03", "open": 104, "high": 107, "low": 103, "close": 106, "volume": 130000},
    )


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


def _contains_forbidden_wording(value: Any) -> bool:
    text = " ".join(_walk_strings(value)).lower()
    return any(re.search(pattern, text) for pattern in FORBIDDEN_PATTERNS)


def _check(check_id: str, passed: bool, detail: str) -> dict:
    return {"check_id": check_id, "passed": bool(passed), "detail": detail}


def run_gateway_backtest_readiness_gate() -> dict:
    """Run deterministic local readiness checks for the next architecture layer."""

    rows = _fixture_rows()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        csv_path = root / "bars.csv"
        jsonl_path = root / "bars.jsonl"
        csv_path.write_text(
            "\n".join(
                [
                    "ticker,timestamp,open,high,low,close,volume",
                    *[
                        f"{row['ticker']},{row['timestamp']},{row['open']},{row['high']},{row['low']},{row['close']},{row['volume']}"
                        for row in rows
                    ],
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        jsonl_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
        store_root = root / "store"
        csv_gateway = run_offline_gateway_to_engine(input_path=str(csv_path), ticker="DEMO", store_root=str(store_root))
        jsonl_gateway = run_offline_gateway_to_engine(input_path=str(jsonl_path), ticker="DEMO")
        written_records = read_llm_readable_records(store_root=str(store_root))

    payload = build_payload_from_local_records(records=rows, ticker="DEMO")
    backtest = run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"]))
    risk_v3 = run_risk_engine_v3(payload=payload)
    readiness = assess_fine_tune_readiness(
        engine_result=csv_gateway.get("engine_result"),
        backtest_result=backtest,
        ml_summary=(csv_gateway.get("engine_result") or {}).get("ml_engine"),
    )
    candidate = build_fine_tune_experiment_candidate(readiness=readiness)
    candidate_validation = validate_fine_tune_candidate(candidate)

    behavior_flags = [
        csv_gateway.get("claim_boundary", {}).get("no_live_data") is True,
        csv_gateway.get("claim_boundary", {}).get("no_provider_calls") is True,
        csv_gateway.get("claim_boundary", {}).get("no_training") is True,
        csv_gateway.get("claim_boundary", {}).get("no_inference") is True,
        csv_gateway.get("claim_boundary", {}).get("no_benchmark_rerun") is True,
        backtest.get("claim_boundary", {}).get("no_benchmark_rerun") is True,
        candidate.get("auto_training_allowed") is False,
        candidate.get("auto_deploy_allowed") is False,
        candidate.get("provider_calls_allowed") is False,
    ]
    checked_payload = {
        "csv_gateway": csv_gateway,
        "jsonl_gateway": jsonl_gateway,
        "backtest": backtest,
        "risk_v3": risk_v3,
        "readiness": readiness,
        "candidate": candidate,
    }
    checks = [
        _check("offline_gateway_contract_exists", csv_gateway.get("claim_boundary", {}).get("offline_gateway_only") is True, "Offline gateway exposes local boundary."),
        _check("csv_records_feed_engine", csv_gateway.get("gateway_status") == "completed" and (csv_gateway.get("engine_result") or {}).get("engine_status", "").startswith("completed"), "CSV fixture feeds Diagnostic Engine."),
        _check("jsonl_records_feed_engine", jsonl_gateway.get("gateway_status") == "completed" and (jsonl_gateway.get("engine_result") or {}).get("engine_status", "").startswith("completed"), "JSONL fixture feeds Diagnostic Engine."),
        _check("llm_records_written_to_temp_store", len(written_records) > 0, "LLM-readable records were written under temp store."),
        _check("dag_backtest_fixture_runs", backtest.get("backtest_status") == "completed" and backtest.get("auto_execution_count") == 0, "Local DAG harness completed without auto execution."),
        _check("risk_v3_runs", risk_v3.get("risk_engine_version") == "v3" and risk_v3.get("risk_engine_status") == "completed", "Risk Engine V3 completed."),
        _check("fine_tune_control_safe_candidate", candidate_validation.get("is_valid") is True and candidate.get("auto_training_allowed") is False, "Fine-tune candidate is safe and review-only."),
        _check("no_live_provider_training_inference_benchmark", all(behavior_flags), "Boundary flags exclude disallowed runtime behavior."),
        _check("no_forbidden_wording", not _contains_forbidden_wording(checked_payload), "Readiness outputs avoid forbidden wording and action labels."),
    ]
    ready = all(check["passed"] for check in checks)
    return {
        "readiness_status": "ready_for_offline_gateway_backtest_and_fine_tune_control" if ready else "attention_required",
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "offline_gateway_status": csv_gateway.get("gateway_status"),
        "jsonl_gateway_status": jsonl_gateway.get("gateway_status"),
        "llm_record_count": len(written_records),
        "backtest_status": backtest.get("backtest_status"),
        "risk_engine_v3_status": risk_v3.get("risk_engine_status"),
        "fine_tune_readiness_level": readiness.get("readiness_level"),
        "human_review_required": True,
        "auto_execution_allowed": False,
        "auto_training_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_gateway_backtest_readiness_report(result: dict) -> str:
    """Render a compact readiness gate report."""

    lines = [
        "# Gateway Backtest Readiness",
        "",
        f"Readiness status: {result.get('readiness_status')}",
        f"Checks passed: {result.get('passed_count')} of {result.get('check_count')}",
        f"Offline gateway: {result.get('offline_gateway_status')}",
        f"JSONL gateway: {result.get('jsonl_gateway_status')}",
        f"LLM record count: {result.get('llm_record_count')}",
        f"DAG harness: {result.get('backtest_status')}",
        f"Risk Engine V3: {result.get('risk_engine_v3_status')}",
        f"Fine-tune readiness: {result.get('fine_tune_readiness_level')}",
        "Human review required: True",
        "Auto execution allowed: False",
        "Auto training allowed: False",
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
            "Offline local-file gateway, local/static harness, diagnostic risk, and experiment-candidate control only.",
            "No live data, provider calls, training, inference, benchmark rerun, server database, or vector database is added.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline gateway/backtest/fine-tune readiness checks.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_gateway_backtest_readiness_gate()
    if args.format == "report":
        print(render_gateway_backtest_readiness_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("readiness_status") == "ready_for_offline_gateway_backtest_and_fine_tune_control" else 1


if __name__ == "__main__":
    raise SystemExit(main())
