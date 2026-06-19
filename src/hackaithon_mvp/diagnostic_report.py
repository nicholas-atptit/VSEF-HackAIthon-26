"""Human-readable diagnostic report renderer for HackAIthon MVP packets."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.evidence_packet import build_evidence_packet


REPORT_TITLE = "HackAIthon MVP Diagnostic Routing Report"


def _join(values: object) -> str:
    if isinstance(values, list):
        return ", ".join(str(value) for value in values) if values else "none"
    return str(values) if values is not None else "not_available"


def render_diagnostic_report(packet: dict) -> str:
    """Render a compact markdown-like report from an evidence packet."""

    forecast = packet.get("forecast_diagnostic_summary", {})
    chain = packet.get("chain_summary", {})
    risk = packet.get("risk_summary", {})
    routing = packet.get("routing_summary", {})
    engine = packet.get("engine_universe_summary", {})
    counts = forecast.get("counts", {}) if isinstance(forecast, dict) else {}

    lines = [
        f"# {REPORT_TITLE}",
        "",
        "## Scope",
        str(packet.get("scope", "Baseline ML-only diagnostic MVP.")),
        f"Run mode: {packet.get('run_mode', 'static_local_review')}",
        "",
        "## Timeframe",
        f"Ticker: {packet.get('ticker', 'not_available')}",
        f"Timeframe: {packet.get('timeframe', 'not_available')} ({packet.get('timeframe_unit', 'not_available')})",
        "",
        "## Diagnostic Summary",
        f"Quant signal: {chain.get('quant_signal', 'not_available')}",
        f"Scenario: {chain.get('scenario', 'not_available')}",
        f"Decision lane: {chain.get('decision_lane', 'not_available')}",
        f"Engines checked: {engine.get('engine_count_checked', 0)}",
        "",
        "## Forecast Diagnostic",
        f"Enabled: {forecast.get('enabled', False)}",
        f"Counts: {counts}",
        "",
        "## Scenario and Risk",
        f"Scenario confidence: {chain.get('scenario_confidence', 'not_available')}",
        f"Risk level: {risk.get('risk_level', 'not_available')}",
        f"Risk flags: {_join(risk.get('risk_flags', []))}",
        "",
        "## Routing",
        f"Route: {routing.get('route', 'not_available')}",
        f"Dashboard status: {routing.get('dashboard_status', 'not_available')}",
        "",
        "## Evidence Boundary",
        *_join(packet.get("claim_boundary", [])).split(", "),
        "",
        "## Human Review Requirement",
        f"Human review required: {bool(packet.get('human_review_required', True))}",
        str(packet.get("non_claim", "Research diagnostic only; human review required.")),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _write_text(path: str, content: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a HackAIthon MVP diagnostic routing report.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--write", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        chain_output = run_diagnostic_chain(args.ticker, sample_size=args.sample_size, timeframe=args.timeframe)
        packet = build_evidence_packet(chain_output)
        report = render_diagnostic_report(packet)
    except ValueError as exc:
        parser.error(str(exc))
    if args.write:
        _write_text(args.write, report)
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
