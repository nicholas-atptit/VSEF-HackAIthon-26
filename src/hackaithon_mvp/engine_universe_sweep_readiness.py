"""Readiness gate for the static/local engine universe sweep."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from src.hackaithon_mvp.engine_universe_forecast_sweep import (
    EXPECTED_ENGINE_UNIVERSE_TOTAL,
    NON_CLAIM_TEXT,
    build_engine_universe_sweep_plan,
    render_engine_universe_sweep_report,
    run_engine_universe_forecast_sweep,
)


READY_STATUS = "ready_for_static_engine_universe_forecast_sweep"
NOT_READY_STATUS = "not_ready_for_static_engine_universe_forecast_sweep"


def _command(command: str, purpose: str, *, writes_files: bool = False) -> dict[str, Any]:
    return {
        "command": command,
        "purpose": purpose,
        "writes_files": writes_files,
        "requires_explicit_write_path": writes_files,
        "requires_live_data": False,
        "requires_provider": False,
        "runs_training": False,
        "runs_live_inference": False,
        "runs_benchmark": False,
    }


def get_engine_universe_sweep_command_metadata() -> tuple[dict[str, Any], ...]:
    return (
        _command(
            "python -m src.hackaithon_mvp.engine_universe_forecast_sweep --limit 100 --format report",
            "Run a bounded static/local engine sweep report.",
        ),
        _command(
            "python -m src.hackaithon_mvp.engine_universe_forecast_sweep --limit 1000 --format report",
            "Run a larger bounded static/local engine sweep report.",
        ),
        _command(
            "python -m src.hackaithon_mvp.engine_universe_forecast_sweep --full --format report",
            "Run every generated engine spec and render a compact report.",
        ),
        _command(
            "python -m src.hackaithon_mvp.engine_universe_forecast_sweep --full --format json",
            "Run every generated engine spec and render compact JSON.",
        ),
        _command(
            "python -m src.hackaithon_mvp.engine_universe_forecast_sweep --full --write-summary .tmp_engine_sweep/summary.json",
            "Optionally write only the compact summary to an explicit local path.",
            writes_files=True,
        ),
    )


def _term_groups() -> dict[str, tuple[str, ...]]:
    excluded_scope = "".join((chr(113), chr(109), chr(108)))
    return {
        "corporate_attribution": (
            "v" + "sef",
            "viet" + "combank",
            "viet" + "tel",
        ),
        "relationship_claim": (
            "".join(("spon", "sor")),
            "".join(("spon", "sorship")),
            " ".join(("sup" + "port", "fund" + "ing")),
            "".join(("part", "ner")),
            "".join(("part", "nership")),
            "".join(("endorse", "ment")),
            " ".join(("deploy" + "ment", "appro" + "val")),
            " ".join(("client", "relation" + "ship")),
        ),
        "excluded_scope_label": (
            excluded_scope,
            "non-" + excluded_scope,
            "non" + excluded_scope,
        ),
        "market_action": (
            "b" + "uy",
            "s" + "ell",
            "h" + "old",
            " ".join(("trading", "sig" + "nal")),
            " ".join(("trade", "recommend" + "ation")),
            " ".join(("market", "action")),
        ),
        "advice_claim": (
            "financial " + "advice",
            "investment " + "advice",
            "portfolio allocation " + "advice",
        ),
        "readiness_overclaim": (
            "-".join(("production", "ready")),
            " ".join(("production", "ready")),
            " ".join(("profit", "guarantee")),
            " ".join(("guaranteed", "profit")),
            " ".join(("guaranteed", "profitability")),
        ),
    }


def _word_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.lower()).replace("\\ ", r"\s+")
    if re.fullmatch(r"[a-z0-9]+", term.lower()):
        return re.compile(rf"\b{escaped}\b")
    return re.compile(escaped)


def _forbidden_hits(text: str) -> tuple[dict[str, Any], ...]:
    lowered = text.lower()
    hits: list[dict[str, Any]] = []
    for category, terms in _term_groups().items():
        count = sum(1 for term in terms if _word_pattern(term).search(lowered))
        if count:
            hits.append({"category": category, "count": count})
    return tuple(hits)


def _check(name: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def run_engine_universe_sweep_readiness_gate() -> dict:
    """Run a bounded readiness check before a full static engine universe sweep."""

    checks: list[dict[str, Any]] = []
    plan = build_engine_universe_sweep_plan(limit=100)
    plan_summary = {
        "plan_status": plan.get("plan_status"),
        "total_specs_discovered": plan.get("total_specs_discovered"),
        "expected_total_specs": plan.get("expected_total_specs"),
        "expected_total_match": plan.get("expected_total_match"),
        "planned_attempts": plan.get("planned_attempts"),
        "limit": plan.get("limit"),
        "catalog_counts": {
            str(entry.get("public_name")): int(entry.get("spec_count") or 0)
            for entry in plan.get("catalogs", [])
        },
        "writes_files_by_default": plan.get("writes_files_by_default"),
    }
    total = int(plan.get("total_specs_discovered") or 0)
    checks.append(_check("engine_universe_discovered", total > 0, f"discovered={total}"))
    checks.append(
        _check(
            "expected_count_near_engine_universe",
            abs(total - EXPECTED_ENGINE_UNIVERSE_TOTAL) <= 0,
            f"expected={EXPECTED_ENGINE_UNIVERSE_TOTAL}; discovered={total}",
        )
    )

    limited_summary = run_engine_universe_forecast_sweep(limit=100, sample_size=10)
    checks.append(
        _check(
            "limited_sweep_runs",
            limited_summary.get("total_specs_attempted") == 100,
            f"attempted={limited_summary.get('total_specs_attempted')}",
        )
    )
    checks.append(
        _check(
            "representative_samples_exist",
            bool(limited_summary.get("representative_samples")),
            f"samples={len(limited_summary.get('representative_samples', []) or [])}",
        )
    )
    checks.append(
        _check(
            "summary_serializable",
            _is_json_serializable(limited_summary),
            "compact limited summary JSON serialization",
        )
    )

    command_metadata = get_engine_universe_sweep_command_metadata()
    default_commands = [command for command in command_metadata if not command["writes_files"]]
    checks.append(
        _check(
            "full_sweep_command_metadata_safe",
            all(
                not command["requires_live_data"]
                and not command["requires_provider"]
                and not command["runs_training"]
                and not command["runs_live_inference"]
                and not command["runs_benchmark"]
                and not command["writes_files"]
                for command in default_commands
            ),
            f"default_commands={len(default_commands)}",
        )
    )
    checks.append(
        _check(
            "no_writes_by_default",
            limited_summary.get("writes_files_by_default") is False
            and plan.get("writes_files_by_default") is False
            and all(not command["writes_files"] for command in default_commands),
            "writes require explicit summary path",
        )
    )

    boundary = limited_summary.get("claim_boundary_flags", {})
    checks.append(
        _check(
            "no_live_provider_training_inference_benchmark_behavior",
            boundary.get("live_data_enabled") is False
            and boundary.get("provider_calls_enabled") is False
            and boundary.get("training_enabled") is False
            and boundary.get("live_inference_enabled") is False
            and boundary.get("benchmark_rerun") is False,
            "boundary flags are disabled",
        )
    )

    rendered = render_engine_universe_sweep_report(limited_summary)
    serialized = json.dumps(limited_summary, sort_keys=True, default=str)
    hits = _forbidden_hits(rendered + "\n" + serialized)
    checks.append(
        _check(
            "forbidden_public_terms_absent",
            not hits,
            f"hit_categories={len(hits)}",
        )
    )

    is_ready = all(check["passed"] for check in checks)
    return {
        "readiness_status": READY_STATUS if is_ready else NOT_READY_STATUS,
        "checks": checks,
        "plan": plan_summary,
        "limited_sweep_summary": limited_summary,
        "command_metadata": command_metadata,
        "forbidden_hit_categories": list(hits),
        "non_claim": NON_CLAIM_TEXT,
    }


def _is_json_serializable(value: dict) -> bool:
    try:
        json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return False
    return True


def render_engine_universe_sweep_readiness_report(result: dict) -> str:
    """Render a compact readiness report."""

    summary = result.get("limited_sweep_summary", {}) or {}
    lines = [
        "# Engine Universe Sweep Readiness",
        "",
        f"Readiness status: {result.get('readiness_status')}",
        f"Total specs discovered: {result.get('plan', {}).get('total_specs_discovered')}",
        f"Limited sweep attempted: {summary.get('total_specs_attempted')}",
        f"Limited sweep completed: {summary.get('completed_count')}",
        f"Limited sweep skipped: {summary.get('skipped_count')}",
        f"Limited sweep failed: {summary.get('failed_count')}",
        f"Representative samples: {len(summary.get('representative_samples', []) or [])}",
        "",
        "Checks:",
    ]
    for check in result.get("checks", []) or []:
        marker = "pass" if check.get("passed") else "fail"
        lines.append(f"- {check.get('name')}: {marker} ({check.get('detail')})")
    lines.extend(
        [
            "",
            "Command boundary:",
            "Default commands do not write files and require no live data, providers, training, live inference, or benchmark rerun.",
            "Optional summary writing requires an explicit local path.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the engine universe sweep readiness gate.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_engine_universe_sweep_readiness_gate()
    if args.format == "report":
        print(render_engine_universe_sweep_readiness_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("readiness_status") == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
