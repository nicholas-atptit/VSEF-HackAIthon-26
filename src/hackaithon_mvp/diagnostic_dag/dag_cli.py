"""CLI for the HackAIthon MVP diagnostic DAG runtime."""

from __future__ import annotations

import argparse
import json
import sys

from src.hackaithon_mvp.quant_core_policy_registry import (
    get_demo_policy_h40_direction_only,
    get_demo_policy_predicted_vs_actual,
)

from .dag_executor import execute_diagnostic_dag
from .dag_registry import build_default_diagnostic_dag, summarize_dag
from .dag_storage_bridge import load_static_context_from_storage, persist_dag_execution
from .dag_validator import validate_dag


def _demo_policy(name: str | None) -> dict | None:
    if name is None:
        return None
    if name == "predicted_vs_actual":
        return get_demo_policy_predicted_vs_actual()
    if name == "h40":
        return get_demo_policy_h40_direction_only()
    raise ValueError(f"unknown policy demo: {name}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the static/local HackAIthon MVP diagnostic DAG.")
    parser.add_argument("--ticker", default="VCB")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--horizon-steps", type=int, default=1)
    parser.add_argument("--policy-demo", choices=("predicted_vs_actual", "h40"), default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--show-dag", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--storage-date", default=None)
    parser.add_argument("--load-storage-context", action="store_true")
    parser.add_argument("--persist-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    nodes = build_default_diagnostic_dag()
    if args.show_dag:
        print(json.dumps(summarize_dag(nodes), indent=2, sort_keys=True))
        return 0
    validation = validate_dag(nodes)
    if args.validate_only:
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0 if validation["is_valid"] else 1
    if (args.load_storage_context or args.persist_run) and not args.storage_root:
        parser.error("--storage-root is required when storage integration flags are used")
    try:
        policy = _demo_policy(args.policy_demo)
        storage_context = None
        if args.load_storage_context:
            storage_context = load_static_context_from_storage(
                storage_root=args.storage_root,
                ticker=args.ticker,
                timeframe=args.timeframe,
                date=args.storage_date,
            )
        result = execute_diagnostic_dag(
            nodes,
            {
                "ticker": args.ticker,
                "timeframe": args.timeframe,
                "horizon_steps": args.horizon_steps,
                "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
                "policy_name": policy.get("policy_name") if isinstance(policy, dict) else None,
            },
            policy=policy,
            storage_context=storage_context,
        )
        if args.persist_run:
            result["storage_persistence"] = persist_dag_execution(result, storage_root=args.storage_root)
    except ValueError as exc:
        parser.error(str(exc))
    if args.format == "report":
        report = result.get("final_state", {}).get("diagnostic_report", {})
        if not report:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("execution_status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
