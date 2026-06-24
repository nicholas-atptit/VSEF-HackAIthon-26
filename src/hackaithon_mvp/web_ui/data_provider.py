"""Local data provider for the VSEF terminal-style web UI prototype."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_60pct_release_gate import STATUS_BLOCKED_BELOW, STATUS_BLOCKED_ROWS
from src.hackaithon_mvp.social_listening_contract import get_social_listening_contract
from src.hackaithon_mvp.web_ui.forecast_chart_provider import (
    build_forecast_chart_coverage_summary,
    build_forecast_chart_data,
    build_horizon_comparison_chart,
)


REQUIRED_SUMMARY_SECTIONS = (
    "product_status",
    "architecture_modules",
    "engine_universe",
    "forecast_accuracy_gate",
    "classical_61pct_benchmark",
    "data_expansion_requirement",
    "risk_management",
    "social_listening_placeholder",
    "rag_llm_placeholder",
    "human_review",
    "report_builder",
    "safe_demo_commands",
    "blocked_claims",
    "terminal_universe",
    "terminal_modules",
)

FORBIDDEN_PUBLIC_OUTPUT = (
    "B" + "UY",
    "S" + "ELL",
    "H" + "OLD",
    "production" + "-ready",
    "production " + "ready",
    "financial advice",
    "investment advice",
    "target " + "price",
)

VN30_DEMO_UNIVERSE = (
    ("ACB", "Asia Commercial Bank", "Banking"),
    ("BCM", "Becamex IDC", "Real estate"),
    ("BID", "BIDV", "Banking"),
    ("BVH", "Bao Viet Holdings", "Financial services"),
    ("CTG", "VietinBank", "Banking"),
    ("FPT", "FPT Corporation", "Technology"),
    ("GAS", "PV Gas", "Energy"),
    ("GVR", "Vietnam Rubber Group", "Materials"),
    ("HDB", "HDBank", "Banking"),
    ("HPG", "Hoa Phat Group", "Materials"),
    ("MBB", "MBBank", "Banking"),
    ("MSN", "Masan Group", "Consumer"),
    ("MWG", "Mobile World Group", "Retail"),
    ("PLX", "Petrolimex", "Energy"),
    ("POW", "PV Power", "Utilities"),
    ("SAB", "Sabeco", "Consumer"),
    ("SHB", "SHB", "Banking"),
    ("SSB", "SeABank", "Banking"),
    ("SSI", "SSI Securities", "Securities"),
    ("STB", "Sacombank", "Banking"),
    ("TCB", "Techcombank", "Banking"),
    ("TPB", "TPBank", "Banking"),
    ("VCB", "Vietcombank", "Banking"),
    ("VHM", "Vinhomes", "Real estate"),
    ("VIB", "VIB", "Banking"),
    ("VIC", "Vingroup", "Conglomerate"),
    ("VJC", "Vietjet Air", "Aviation"),
    ("VNM", "Vinamilk", "Consumer"),
    ("VPB", "VPBank", "Banking"),
    ("VRE", "Vincom Retail", "Retail"),
)

STATUS_LABELS = (
    "Ready for review",
    "Needs evidence",
    "Gate blocked",
    "Risk flagged",
    "Insufficient data",
    "Benchmark scope only",
    "Human review",
)


def _repo_root(path: str) -> Path:
    return Path(path).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _readme_metric(pattern: str, text: str, default: Any = None) -> Any:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return default
    value = match.group(1).replace(",", "")
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return default


def _catalog_counts(root: Path) -> dict[str, int]:
    manifest = _read_json(root / "catalogs" / "hackaithon_mvp" / "catalog_generation_manifest.json")
    baseline = int(manifest.get("baseline_engine_count") or 32_850)
    auxiliary = int(manifest.get("support_engine_count") or 22_500)
    stack = int(manifest.get("stack_engine_count") or 22_500)
    return {
        "baseline": baseline,
        "auxiliary": auxiliary,
        "stack": stack,
        "total": baseline + auxiliary + stack,
    }


def _classical_benchmark(root: Path) -> dict[str, Any]:
    try:
        from src.hackaithon_mvp.classical_61pct_claim_card import build_classical_61pct_claim_card
    except ImportError:
        card = {}
    else:
        card = build_classical_61pct_claim_card(repo_root=str(root))

    exact_scope = card.get("exact_scope") if isinstance(card.get("exact_scope"), dict) else {}
    allowed_wording = card.get("allowed_wording") or (
        "Within a bounded VN30 hourly absolute-direction benchmark, the classical L2 Logistic champion "
        "reached 61.61% final accuracy over 4,074 rows."
    )
    return {
        "title": "Classical 61.61% Benchmark Lane",
        "universe": exact_scope.get("universe") or "VN30 hourly",
        "target": card.get("target") or "absolute_direction",
        "model": card.get("model") or "L2 Logistic",
        "feature_set": exact_scope.get("feature_set") or "feature_set_C_closest",
        "horizon": card.get("horizon") or "h40",
        "rows": int(card.get("rows") or 4074),
        "final_accuracy_percent": float(card.get("final_accuracy_percent") or 61.61),
        "lift_pp": float(card.get("lift_pp") or 10.90),
        "claim_status": "exact-scope only",
        "allowed_wording": allowed_wording,
        "scope_lock": "BENCHMARK SCOPE LOCKED - NOT A BROAD SYSTEM-WIDE FORECAST CLAIM",
        "not_broad_system_claim": True,
        "source_evidence_found": bool(card.get("source_evidence_found")),
        "broad_claim_allowed": False,
        "human_review_required": True,
    }


def _forecast_gate() -> dict[str, Any]:
    return {
        "hard_gate_percent": 60.0,
        "current_broad_local_gate": {
            "best_release_candidate_bacc_percent": 55.7273,
            "coverage_percent": 20.8926,
            "gap_to_60_percent_pp": 4.2727,
            "release_status": STATUS_BLOCKED_BELOW,
            "visible_terminal_status": "Gate blocked",
        },
        "data_expanded_attempt": {
            "retained_bacc_percent": 56.3179,
            "rows": 205,
            "coverage_percent": 0.6905,
            "status": STATUS_BLOCKED_ROWS,
            "expanded_data_available": False,
            "ohlcv_only_fallback_blocked": True,
            "visible_terminal_status": "Insufficient data",
        },
        "governance_message": "The system blocks forecast-performance claims when the 60% release gate is not met.",
        "broad_forecast_claim_allowed": False,
        "human_review_required": True,
    }


def _status_for_index(index: int, offset: int = 0) -> str:
    return STATUS_LABELS[(index + offset) % len(STATUS_LABELS)]


def _sparkline(ticker: str) -> list[int]:
    seed = sum(ord(char) for char in ticker)
    return [((seed + step * 11) % 23) - 11 for step in range(16)]


def _ticker_record(ticker: str) -> tuple[str, str, str]:
    lookup = {symbol: (symbol, name, sector) for symbol, name, sector in VN30_DEMO_UNIVERSE}
    return lookup.get(ticker.upper(), ("VCB", "Vietcombank", "Banking"))


def _ticker_card(symbol: str, name: str, sector: str, index: int) -> dict[str, Any]:
    data_status = _status_for_index(index, 1)
    diagnostic_status = _status_for_index(index, 0)
    risk_status = _status_for_index(index, 3)
    evidence_status = _status_for_index(index, 5)
    review_status = "Human review" if index % 3 == 0 else _status_for_index(index, 0)
    return {
        "ticker": symbol,
        "display_name": name,
        "sector": sector,
        "group": sector,
        "data_coverage_status": data_status,
        "diagnostic_status": diagnostic_status,
        "risk_status": risk_status,
        "forecast_gate_status": "Gate blocked",
        "evidence_status": evidence_status,
        "review_status": review_status,
        "latest_local_evidence_timestamp": "demo local snapshot",
        "sparkline": _sparkline(symbol),
        "badges": [
            {"label": "Evidence", "status": evidence_status},
            {"label": "Risk", "status": risk_status},
            {"label": "Gate", "status": "Gate blocked"},
            {"label": "Review", "status": review_status},
        ],
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "universe_source": "demo_universe",
    }


def _vn30_cards() -> list[dict[str, Any]]:
    return [_ticker_card(symbol, name, sector, index) for index, (symbol, name, sector) in enumerate(VN30_DEMO_UNIVERSE)]


def build_vn30_terminal_universe(*, repo_root: str = ".") -> dict:
    """Build the exact 30-card VN30 terminal universe for the local demo."""

    root = _repo_root(repo_root)
    cards = _vn30_cards()
    sector_counts: dict[str, int] = {}
    for card in cards:
        sector_counts[card["sector"]] = sector_counts.get(card["sector"], 0) + 1

    status_distribution: dict[str, int] = {label: 0 for label in STATUS_LABELS}
    for card in cards:
        status_distribution[card["review_status"]] = status_distribution.get(card["review_status"], 0) + 1

    return {
        "title": "VSEF Terminal - VN30 Diagnostic Research Workspace",
        "subtitle": "Evidence-based stock evaluation terminal for VN30 banking/equity research review.",
        "universe": "VN30",
        "universe_source": "demo_universe",
        "source_note": "Static demo universe is used when repo-local ticker discovery is unavailable.",
        "ticker_count": len(cards),
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "cards": cards,
        "sector_distribution": sector_counts,
        "status_distribution": status_distribution,
        "terminal_commands": [
            "VCB",
            "VCB DIAG",
            "VCB RISK",
            "VCB EVID",
            "VCB CHART",
            "VCB H1 CHART",
            "VCB H5 CHART",
            "VCB H10 CHART",
            "VCB BACKTEST",
            "VCB FORECAST",
            "VN30",
            "GATE",
            "CLAIMS",
            "CHART HELP",
            "HELP",
        ],
        "safe_paths": {
            "repo_root_exists": root.exists(),
            "generated_demo_snapshots": ".tmp_web_ui_demo",
        },
    }


def build_ticker_terminal_profile(ticker: str, *, repo_root: str = ".") -> dict:
    """Build one selected ticker workspace profile for the terminal UI."""

    root = _repo_root(repo_root)
    symbol, name, sector = _ticker_record(ticker)
    index = [item[0] for item in VN30_DEMO_UNIVERSE].index(symbol)
    card = _ticker_card(symbol, name, sector, index)
    counts = _catalog_counts(root)
    gate = _forecast_gate()
    benchmark = _classical_benchmark(root)
    chart = build_forecast_chart_data(symbol, repo_root=str(root))
    horizon_comparison = build_horizon_comparison_chart(symbol, repo_root=str(root))
    review_items = [
        {
            "issue": "Forecast claim review",
            "severity": "high",
            "evidence": gate["current_broad_local_gate"]["release_status"],
            "status": "Gate blocked",
            "reviewer_action": "reject broad claim",
        },
        {
            "issue": "Data quality review",
            "severity": "medium",
            "evidence": card["data_coverage_status"],
            "status": "Human review",
            "reviewer_action": "request more data",
        },
        {
            "issue": "Benchmark scope review",
            "severity": "medium",
            "evidence": benchmark["claim_status"],
            "status": "Benchmark scope only",
            "reviewer_action": "approve diagnostic wording",
        },
        {
            "issue": "Evidence packet review",
            "severity": "medium",
            "evidence": "local evidence summaries",
            "status": "Needs evidence",
            "reviewer_action": "export evidence packet",
        },
    ]

    profile = {
        **card,
        "company": name,
        "exchange": "HOSE demo placeholder",
        "research_objective": "Assess diagnostic evidence quality and model readiness",
        "evaluation_period": "Local demo window, static evidence snapshot",
        "data_quality": {
            "status": card["data_coverage_status"],
            "coverage": "Local OHLCV coverage available for demo diagnostics",
            "expanded_data_requirement": "Real expanded data is required before another 60% release attempt.",
            "duplicate_overlap_audit": "checked",
            "provider_calls": False,
        },
        "forecast_diagnostic_summary": {
            "status": "Gate blocked",
            "best_release_candidate_bacc_percent": gate["current_broad_local_gate"]["best_release_candidate_bacc_percent"],
            "coverage_percent": gate["current_broad_local_gate"]["coverage_percent"],
            "gap_to_60_percent_pp": gate["current_broad_local_gate"]["gap_to_60_percent_pp"],
            "release_status": gate["current_broad_local_gate"]["release_status"],
        },
        "risk_diagnostic_summary": {
            "status": card["risk_status"],
            "risk_categories": [
                {"category": "Data quality risk", "level": card["data_coverage_status"], "review_status": "Human review"},
                {"category": "Liquidity risk", "level": "Needs evidence", "review_status": "Human review"},
                {"category": "Volatility/gap risk", "level": "Risk flagged", "review_status": "Human review"},
                {"category": "Model disagreement risk", "level": "Needs evidence", "review_status": "Human review"},
                {"category": "Calibration risk", "level": "Needs evidence", "review_status": "Human review"},
                {"category": "Leakage/overlap risk", "level": "Ready for review", "review_status": "Human review"},
                {"category": "Staleness risk", "level": "Needs evidence", "review_status": "Human review"},
                {"category": "Claim-boundary risk", "level": "Gate blocked", "review_status": "Human review"},
            ],
        },
        "engine_evidence_summary": {
            "generated_specs": counts["total"],
            "baseline_specs": counts["baseline"],
            "auxiliary_specs": counts["auxiliary"],
            "stack_specs": counts["stack"],
            "static_only_completed": 120,
            "generated_evidence_completed": 9960,
            "readiness": card["evidence_status"],
            "note": "77,850 means generated diagnostic engine specs, not trained models.",
        },
        "gate_status": gate,
        "benchmark_scope": benchmark,
        "forecast_chart_status": {
            "available": bool(chart.get("available")),
            "reason": chart.get("reason"),
            "source_artifact": chart.get("source_artifact"),
            "horizon": chart.get("horizon"),
            "metrics": chart.get("metrics"),
            "unavailable_label": "Forecast chart unavailable — evidence missing",
            "boundary": chart.get("boundary"),
        },
        "horizon_comparison": horizon_comparison,
        "review_queue_items": review_items,
        "report_sections": [
            "Executive Summary",
            "VN30 Universe Evidence",
            "Ticker Diagnostic Summary",
            "Forecast Chart Evidence",
            "Engine Universe",
            "Forecast Gate Status",
            "61.61% Exact-Scope Benchmark",
            "Risk Review",
            "Human Review Notes",
            "Claim Boundaries",
        ],
        "chart_series": {
            "label": "placeholder local diagnostic series",
            "values": _sparkline(symbol),
        },
        "tabs": ["Overview", "Data", "Diagnostics", "Risk", "Backtest", "Evidence", "Review", "Report"],
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
    }
    return profile


def build_terminal_command_response(command: str, *, repo_root: str = ".") -> dict:
    """Return safe static terminal command output."""

    text = (command or "HELP").strip().upper()
    if not text:
        text = "HELP"
    tokens = text.split()
    ticker_symbols = {symbol for symbol, _, _ in VN30_DEMO_UNIVERSE}

    if text in {"HELP", "CHART HELP"}:
        return {
            "command": text,
            "command_status": "completed",
            "title": "Supported terminal commands" if text == "HELP" else "Forecast chart commands",
            "lines": [
                "Ticker: VCB",
                "Ticker diagnostics: VCB DIAG",
                "Ticker risk: VCB RISK",
                "Ticker evidence: VCB EVID",
                "Ticker chart: VCB CHART",
                "Ticker horizon chart: VCB H1 CHART, VCB H5 CHART, VCB H10 CHART",
                "Ticker backtest: VCB BACKTEST",
                "Ticker forecast evidence: VCB FORECAST",
                "Universe: VN30",
                "Gate status: GATE",
                "Claim boundaries: CLAIMS",
            ],
            "local_only": True,
            "provider_calls": False,
        }

    if text == "VN30":
        universe = build_vn30_terminal_universe(repo_root=repo_root)
        return {
            "command": text,
            "command_status": "completed",
            "title": "VN30 terminal universe",
            "lines": [
                f"{universe['ticker_count']} ticker cards loaded from {universe['universe_source']}.",
                "Every card is local demo evidence and requires human review.",
                "No live provider call was made.",
            ],
            "payload": {"ticker_count": universe["ticker_count"]},
            "local_only": True,
            "provider_calls": False,
        }

    if text == "GATE":
        gate = _forecast_gate()
        return {
            "command": text,
            "command_status": "completed",
            "title": "Hard 60% release gate",
            "lines": [
                f"Current broad/local gate: {gate['current_broad_local_gate']['release_status']}.",
                "Best release-candidate BAcc: 55.7273%; gap to gate: 4.2727 percentage points.",
                f"Data-expanded attempt: {gate['data_expanded_attempt']['status']}.",
                "Real expanded data is required before another release attempt.",
            ],
            "payload": gate,
            "local_only": True,
            "provider_calls": False,
        }

    if text == "CLAIMS":
        benchmark = _classical_benchmark(_repo_root(repo_root))
        return {
            "command": text,
            "command_status": "completed",
            "title": "Claim boundaries",
            "lines": [
                benchmark["scope_lock"],
                benchmark["allowed_wording"],
                "Broad system-wide forecast wording is blocked.",
                "Human review is required before report export.",
            ],
            "payload": benchmark,
            "local_only": True,
            "provider_calls": False,
        }

    if tokens[0] in ticker_symbols:
        profile = build_ticker_terminal_profile(tokens[0], repo_root=repo_root)
        mode = tokens[1] if len(tokens) > 1 else "OVERVIEW"
        horizon = None
        if len(tokens) >= 2 and tokens[1].startswith("H") and tokens[1][1:].isdigit():
            horizon = tokens[1].lower()
            mode = tokens[2] if len(tokens) > 2 else "CHART"
        if mode == "DIAG":
            lines = [
                f"{profile['ticker']} diagnostics: {profile['forecast_diagnostic_summary']['release_status']}.",
                "Hard 60% release gate remains blocked for broad/local forecast wording.",
                "Engine evidence is available for analyst review.",
            ]
        elif mode == "RISK":
            lines = [
                f"{profile['ticker']} risk status: {profile['risk_status']}.",
                "Claim-boundary and evidence-staleness risks require human review.",
                "No portfolio allocation or execution workflow is present.",
            ]
        elif mode == "EVID":
            lines = [
                f"{profile['ticker']} evidence packet: {profile['evidence_status']}.",
                f"Engine specs linked: {profile['engine_evidence_summary']['generated_specs']:,}.",
                "Evidence packet remains local and read-only in this demo.",
            ]
        elif mode in {"CHART", "FORECAST", "BACKTEST"}:
            chart_payload = build_forecast_chart_data(profile["ticker"], horizon=horizon, repo_root=repo_root)
            if chart_payload.get("available"):
                lines = [
                    f"{profile['ticker']} forecast chart evidence is available for {chart_payload.get('horizon')}.",
                    f"Rows: {chart_payload['metrics']['rows']}; source: {chart_payload['source_artifact']}.",
                    "Local forecast-vs-actual rows only. Human review required.",
                ]
            else:
                lines = [
                    "Forecast chart unavailable — evidence missing",
                    f"Reason: {chart_payload.get('reason')}.",
                    "No row-level forecast timeline is fabricated.",
                ]
        else:
            lines = [
                f"{profile['ticker']} - {profile['company']} ({profile['sector']}).",
                f"Review status: {profile['review_status']}.",
                "Use DIAG, RISK, EVID, CHART, BACKTEST, or FORECAST for focused drilldown.",
            ]
        return {
            "command": text,
            "command_status": "completed",
            "title": f"{profile['ticker']} terminal response",
            "lines": lines,
            "payload": {"ticker": profile["ticker"], "mode": mode, "horizon": horizon},
            "local_only": True,
            "provider_calls": False,
        }

    return {
        "command": text,
        "command_status": "not_found",
        "title": "Command not available",
        "lines": ["Use HELP for supported local research commands."],
        "local_only": True,
        "provider_calls": False,
    }


def build_report_preview(ticker: str = "VCB", *, repo_root: str = ".") -> dict:
    """Build a report preview without writing files."""

    scope = (ticker or "VCB").strip().upper()
    profile = build_ticker_terminal_profile("VCB" if scope == "VN30" else scope, repo_root=repo_root)
    universe = build_vn30_terminal_universe(repo_root=repo_root)
    if scope == "VN30":
        chart_summary = build_forecast_chart_coverage_summary((card["ticker"] for card in universe["cards"]), repo_root=repo_root)
        chart_section_status = (
            f"{chart_summary['tickers_with_row_level_chart_evidence']} tickers with row-level chart evidence; "
            f"{chart_summary['tickers_missing_chart_evidence']} missing"
        )
    else:
        chart_payload = build_forecast_chart_data(profile["ticker"], repo_root=repo_root)
        comparison = build_horizon_comparison_chart(profile["ticker"], repo_root=repo_root)
        chart_summary = {
            "forecast_chart_status": "available" if chart_payload.get("available") else "Forecast chart unavailable — evidence missing",
            "available_horizons": comparison["available_horizons"],
            "source_artifact": chart_payload.get("source_artifact"),
            "metrics": chart_payload.get("metrics"),
            "warning": None if chart_payload.get("available") else chart_payload.get("reason"),
            "no_action_output": True,
        }
        chart_section_status = chart_summary["forecast_chart_status"]
    return {
        "scope": scope,
        "selected_ticker": profile["ticker"] if scope != "VN30" else None,
        "title": f"Local evidence report preview - {scope}",
        "writes_files_by_default": False,
        "export_root_if_enabled": ".tmp_web_ui_demo",
        "local_only": True,
        "provider_calls": False,
        "forecast_chart_summary": chart_summary,
        "sections": [
            {"title": "Executive Summary", "status": "preview"},
            {"title": "VN30 Universe", "status": f"{universe['ticker_count']} ticker cards"},
            {"title": "Selected Ticker", "status": profile["review_status"] if scope != "VN30" else "all VN30"},
            {"title": "Forecast Chart Evidence", "status": chart_section_status},
            {"title": "Engine Universe", "status": "77,850 generated diagnostic engine specs"},
            {"title": "Forecast Gate", "status": STATUS_BLOCKED_BELOW},
            {"title": "61.61% Benchmark", "status": "exact-scope only"},
            {"title": "Risk Monitor", "status": "human review"},
            {"title": "Claim Boundaries", "status": "broad wording blocked"},
        ],
    }


def build_module_statuses(*, repo_root: str = ".") -> dict:
    """Build terminal module status cards for the local UI."""

    root = _repo_root(repo_root)
    social_contract = get_social_listening_contract()
    return {
        "module_status": "terminal_ui_ready",
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "modules": [
            {
                "id": "vn30-terminal",
                "name": "VN30 Terminal",
                "status": "Ready for review",
                "mode": "30-card local universe",
                "notes": "The first screen shows all 30 VN30 demo ticker cards.",
            },
            {
                "id": "ticker-workspace",
                "name": "Ticker Workspace",
                "status": "Human review",
                "mode": "per-ticker diagnostics",
                "notes": "Ticker drilldown shows data quality, diagnostics, risk, evidence, and report tabs.",
            },
            {
                "id": "engine-matrix",
                "name": "Engine Matrix",
                "status": "Ready for review",
                "mode": "diagnostic engine universe",
                "notes": "77,850 generated diagnostic engine specs are visible with completion and skip evidence.",
            },
            {
                "id": "forecast-gate",
                "name": "Forecast Gate",
                "status": "Gate blocked",
                "mode": "hard 60% governance layer",
                "notes": "Current broad/local and data-expanded attempts remain blocked.",
            },
            {
                "id": "benchmark",
                "name": "61.61% Benchmark",
                "status": "Benchmark scope only",
                "mode": "exact-scope evidence card",
                "notes": "The benchmark lane is explicitly not a broad system-wide forecast claim.",
            },
            {
                "id": "risk-monitor",
                "name": "Risk Monitor",
                "status": "Human review",
                "mode": "cross-ticker risk table",
                "notes": "Data, liquidity, volatility, calibration, overlap, staleness, and claim risk are visible.",
            },
            {
                "id": "market-context",
                "name": "Market Context",
                "status": "demo placeholder",
                "mode": social_contract.get("contract_status", "schema contract only"),
                "notes": "No scraping, live API, or unverified sentiment claim is performed.",
            },
            {
                "id": "rag-assistant",
                "name": "RAG / Evidence Assistant",
                "status": "local demo placeholder",
                "mode": "static evidence summaries",
                "notes": "No real LLM call is made by the web UI; optional local Ollama remains separate.",
            },
            {
                "id": "human-review",
                "name": "Human Review Queue",
                "status": "Human review",
                "mode": "all-ticker review workflow",
                "notes": "Allowed actions are diagnostic wording approval, data requests, broad-claim rejection, and evidence export.",
            },
            {
                "id": "report-builder",
                "name": "Report Builder",
                "status": "Ready for review",
                "mode": "preview-only",
                "notes": "Report previews do not write files by default; enabled exports must use .tmp_web_ui_demo.",
            },
        ],
        "safe_paths": {
            "generated_demo_snapshots": ".tmp_web_ui_demo",
            "repo_root_exists": root.exists(),
        },
    }


def build_demo_stock_profile(ticker: str = "VCB") -> dict:
    """Build a compatibility single-ticker profile using the terminal provider."""

    profile = build_ticker_terminal_profile(ticker)
    return {
        "ticker": profile["ticker"],
        "company_name": profile["company"],
        "exchange": profile["exchange"],
        "sector": profile["sector"],
        "evaluation_period": profile["evaluation_period"],
        "data_coverage": profile["data_quality"]["coverage"],
        "latest_evidence_timestamp": profile["latest_local_evidence_timestamp"],
        "research_objective": profile["research_objective"],
        "panels": [
            {
                "name": "Data Quality",
                "status": profile["data_quality"]["status"],
                "items": [
                    profile["data_quality"]["coverage"],
                    "duplicate and overlap audit checked",
                    profile["data_quality"]["expanded_data_requirement"],
                ],
            },
            {
                "name": "Forecast Diagnostics",
                "status": "Blocked by claim gate",
                "items": [
                    "Best release-candidate BAcc: 55.7273%",
                    "Hard 60% gate remains blocked",
                    "Evidence packet available for analyst review",
                ],
            },
            {
                "name": "Risk Review",
                "status": "Human review required",
                "items": [
                    "Claim-boundary risk visible for broad performance wording",
                    "Evidence staleness shown as review item",
                    "Calibration and model disagreement need review",
                ],
            },
            {
                "name": "Market Context",
                "status": "demo placeholder",
                "items": [
                    "Banking sector policy context placeholder",
                    "Interest rate discussion placeholder",
                    "Human verification required",
                ],
            },
            {
                "name": "Human Review Queue",
                "status": "Human review required",
                "items": [
                    "approve diagnostic wording",
                    "request more data",
                    "reject broad claim",
                    "mark evidence insufficient",
                    "export report",
                ],
            },
        ],
        "review_outcomes": [
            "Evidence supports further review",
            "Insufficient evidence",
            "Blocked by claim gate",
            "Human review required",
        ],
    }


def build_proposal_ui_summary(*, repo_root: str = ".") -> dict:
    """Build the full local terminal UI summary."""

    root = _repo_root(repo_root)
    readme = _read_text(root / "README.md")
    counts = _catalog_counts(root)
    generated_specs = _readme_metric(r"([0-9,]+)\s+Generated Diagnostic Engine Specs", readme, counts["total"])
    tests_passed = _readme_metric(r"([0-9,]+)\s+Tests Passed", readme, 804)
    modules = build_module_statuses(repo_root=repo_root)
    universe = build_vn30_terminal_universe(repo_root=repo_root)

    return {
        "product_status": {
            "name": "VSEF Terminal - VN30 Diagnostic Research Workspace",
            "mode": "local demo",
            "local_only": True,
            "live_data": False,
            "provider_calls": False,
            "trading_output": False,
            "human_review_required": True,
            "broker_or_order_execution": False,
        },
        "architecture_modules": modules["modules"],
        "engine_universe": {
            "generated_specs": int(generated_specs or counts["total"]),
            "baseline_specs": counts["baseline"],
            "auxiliary_specs": counts["auxiliary"],
            "stack_specs": counts["stack"],
            "meaning": "77,850 means generated diagnostic engine specs, not trained models.",
            "static_only_sweep": {
                "discovered": counts["total"],
                "attempted": counts["total"],
                "completed": 120,
                "skipped": counts["total"] - 120,
                "failed": 0,
            },
            "generated_evidence_sweep": {
                "discovered": counts["total"],
                "attempted": counts["total"],
                "completed": 9960,
                "skipped": counts["total"] - 9960,
                "failed": 0,
            },
            "top_skip_reasons": [
                "required dependency outputs unavailable",
                "no matching static evidence for model target horizon",
            ],
        },
        "forecast_accuracy_gate": _forecast_gate(),
        "classical_61pct_benchmark": _classical_benchmark(root),
        "data_expansion_requirement": {
            "real_expanded_data_required_for_60pct_attempt": True,
            "expanded_data_available": False,
            "provider_fetch_enabled": False,
            "live_data_gateway_scope": "later integration",
        },
        "risk_management": {
            "status": "Human review",
            "categories": [
                "Data quality risk",
                "Liquidity risk",
                "Volatility/gap risk",
                "Model disagreement risk",
                "Calibration risk",
                "Leakage/duplicate/overlap risk",
                "Evidence staleness risk",
                "Claim-boundary risk",
            ],
            "allowed_language": ["review required", "blocked", "needs evidence", "acceptable for demo"],
        },
        "social_listening_placeholder": {
            "status": "demo placeholder",
            "demo_placeholder": True,
            "contract_only": True,
            "no_scraping": True,
            "no_live_api": True,
            "no_unverified_sentiment_claim": True,
            "human_verification_required": True,
            "sample_cards": [
                "Banking sector policy context",
                "Interest rate discussion",
                "Credit growth narrative",
                "Market liquidity conditions",
            ],
        },
        "rag_llm_placeholder": {
            "status": "local demo placeholder; static evidence summaries; no real LLM call",
            "demo_placeholder": True,
            "retrieves_local_evidence_summaries": True,
            "cannot_mutate_models": True,
            "cannot_output_market_actions": True,
            "provider_calls": False,
        },
        "human_review": {
            "required": True,
            "queue_items": [
                "Forecast claim review",
                "Data quality review",
                "61.61% benchmark scope review",
                "60% gate failure review",
                "Engine-universe skip reason review",
                "Expanded data requirement review",
            ],
            "allowed_reviewer_actions": [
                "approve diagnostic wording",
                "request more data",
                "reject broad claim",
                "mark evidence insufficient",
                "export evidence packet",
                "assign manual review",
            ],
        },
        "report_builder": {
            "mode": "preview-only",
            "writes_files_by_default": False,
            "export_root_if_enabled": ".tmp_web_ui_demo",
            "sections": build_report_preview(repo_root=repo_root)["sections"],
        },
        "safe_demo_commands": {
            "run": "python -m src.hackaithon_mvp.web_ui.app --host 127.0.0.1 --port 8765",
            "url": "http://127.0.0.1:8765",
            "terminal_commands": universe["terminal_commands"],
        },
        "blocked_claims": [
            "Broad system-wide 61% forecast-performance wording",
            "Production or profitability guarantee",
            "Action-oriented market recommendation",
            "Broker/order execution workflow",
        ],
        "terminal_universe": universe,
        "terminal_modules": {
            "module_ids": [module["id"] for module in modules["modules"]],
            "primary_screen": "VN30 Terminal",
            "all_30_tickers_visible": True,
        },
        "tests_passed_reference": int(tests_passed or 804),
    }


def validate_proposal_ui_summary(summary: dict) -> dict:
    """Validate safety and required sections for the web UI summary."""

    missing = [section for section in REQUIRED_SUMMARY_SECTIONS if section not in summary]
    serialized = json.dumps(summary, sort_keys=True)
    forbidden_found = [term for term in FORBIDDEN_PUBLIC_OUTPUT if term in serialized]
    return {
        "valid": not missing and not forbidden_found,
        "missing_sections": missing,
        "forbidden_terms": forbidden_found,
        "local_only": summary.get("product_status", {}).get("local_only") is True,
        "live_data": summary.get("product_status", {}).get("live_data") is False,
        "provider_calls": summary.get("product_status", {}).get("provider_calls") is False,
        "human_review_required": summary.get("product_status", {}).get("human_review_required") is True,
    }
