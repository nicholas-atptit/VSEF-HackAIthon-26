"""Data provider for the local VSEF web UI prototype."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.engine_universe_gap_analysis import run_engine_universe_gap_analysis
from src.hackaithon_mvp.forecast_60pct_release_gate import STATUS_BLOCKED_BELOW, STATUS_BLOCKED_ROWS
from src.hackaithon_mvp.social_listening_contract import get_social_listening_contract


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
)

FORBIDDEN_PUBLIC_OUTPUT = (
    "BUY",
    "SELL",
    "HOLD",
    "production-ready",
    "production ready",
    "financial advice",
    "investment advice",
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
    allowed_wording = card.get("allowed_wording") or (
        "Within a bounded VN30 hourly absolute-direction benchmark, the classical L2 Logistic champion "
        "reached 61.61% final accuracy over 4,074 rows."
    )
    return {
        "title": "Classical 61.61% Benchmark Lane",
        "universe": (card.get("exact_scope") or {}).get("universe") or "VN30 hourly",
        "target": card.get("target") or "absolute_direction",
        "model": card.get("model") or "L2 Logistic",
        "feature_set": (card.get("exact_scope") or {}).get("feature_set") or "feature_set_C_closest",
        "horizon": card.get("horizon") or "h40",
        "rows": int(card.get("rows") or 4074),
        "final_accuracy_percent": float(card.get("final_accuracy_percent") or 61.61),
        "lift_pp": float(card.get("lift_pp") or 10.90),
        "claim_status": "exact-scope only",
        "allowed_wording": allowed_wording,
        "not_broad_system_claim": True,
        "source_evidence_found": bool(card.get("source_evidence_found")),
        "broad_claim_allowed": False,
        "human_review_required": True,
    }


def build_module_statuses(*, repo_root: str = ".") -> dict:
    """Build proposal module status cards for the local UI."""

    root = _repo_root(repo_root)
    social_contract = get_social_listening_contract()
    return {
        "module_status": "proposal_ui_ready",
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "modules": [
            {
                "id": "data-platform",
                "name": "Data Platform",
                "status": "local evidence available",
                "mode": "local files and contracts",
                "notes": "Local OHLCV and evidence-store architecture are visible; expanded data remains a requirement.",
            },
            {
                "id": "forecast-engine",
                "name": "Forecast / Diagnostic Engine Layer",
                "status": "demo-ready diagnostics",
                "mode": "baseline and classical ML diagnostics",
                "notes": "Generated engine specs execute or skip safely under local evidence rules.",
            },
            {
                "id": "risk-engine",
                "name": "Risk Management Engine",
                "status": "review required",
                "mode": "diagnostic risk scoring",
                "notes": "Data quality, calibration, overlap, staleness, and claim-boundary risk are surfaced.",
            },
            {
                "id": "backtesting",
                "name": "Backtesting / Evaluation Layer",
                "status": "evidence visible",
                "mode": "local final-holdout evaluation",
                "notes": "The hard 60% release gate blocks unsupported forecast-performance claims.",
            },
            {
                "id": "market-context",
                "name": "Social Listening / Market Context Layer",
                "status": "demo placeholder",
                "mode": social_contract.get("contract_status", "schema contract only"),
                "notes": "No scraping, live API, or unverified sentiment claim is performed.",
            },
            {
                "id": "rag-llm",
                "name": "RAG + LLM Explanation Layer",
                "status": "local read-only placeholder",
                "mode": "static evidence summaries",
                "notes": "No real LLM call is made by the web UI; optional local Ollama remains separate.",
            },
            {
                "id": "human-review",
                "name": "Human-in-the-loop Review Workspace",
                "status": "required",
                "mode": "review queue",
                "notes": "Claim wording, missing data, and evidence packets require analyst review.",
            },
            {
                "id": "report-export",
                "name": "Report / Evidence Export Layer",
                "status": "preview-only in web UI",
                "mode": "local evidence report",
                "notes": "Generated snapshots, when added later, must remain under .tmp_web_ui_demo.",
            },
        ],
        "safe_paths": {
            "generated_demo_snapshots": ".tmp_web_ui_demo",
            "repo_root_exists": root.exists(),
        },
    }


def build_demo_stock_profile(ticker: str = "VCB") -> dict:
    """Build a safe single-stock diagnostic profile for the local UI."""

    symbol = (ticker or "VCB").strip().upper()
    profiles = {
        "VCB": {
            "ticker": "VCB",
            "company_name": "Vietcombank",
            "exchange": "HOSE placeholder",
            "sector": "Banking",
        },
        "MBB": {
            "ticker": "MBB",
            "company_name": "Military Commercial Joint Stock Bank",
            "exchange": "HOSE placeholder",
            "sector": "Banking",
        },
        "FPT": {
            "ticker": "FPT",
            "company_name": "FPT Corporation",
            "exchange": "HOSE placeholder",
            "sector": "Technology",
        },
    }
    base = profiles.get(symbol, profiles["VCB"])
    return {
        **base,
        "evaluation_period": "Local demo window, static evidence snapshot",
        "data_coverage": "OHLCV local data sufficient for diagnostics; expanded context still required for 60% attempt",
        "latest_evidence_timestamp": "demo placeholder",
        "research_objective": "Assess diagnostic evidence quality and model readiness",
        "panels": [
            {
                "name": "Data Quality",
                "status": "sufficient for demo",
                "items": [
                    "OHLCV local rows available",
                    "duplicate and overlap audit checked",
                    "expanded context required before broader release attempt",
                ],
            },
            {
                "name": "Forecast Diagnostics",
                "status": "blocked by claim gate",
                "items": [
                    "Best release-candidate BAcc: 55.7273%",
                    "Hard 60% gate remains blocked",
                    "Evidence packet available for analyst review",
                ],
            },
            {
                "name": "Risk Review",
                "status": "review required",
                "items": [
                    "Claim-boundary risk high for broad performance wording",
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
                "status": "human review required",
                "items": [
                    "Evidence supports further review",
                    "Reject broad performance overclaim",
                    "Request more data for expanded-data gate",
                ],
            },
        ],
        "safe_statuses": [
            "Evidence supports further review",
            "Insufficient evidence",
            "Blocked by claim gate",
            "Human review required",
        ],
        "local_only": True,
        "provider_calls": False,
    }


def build_proposal_ui_summary(*, repo_root: str = ".") -> dict:
    """Build the complete local proposal UI summary."""

    root = _repo_root(repo_root)
    readme = _read_text(root / "README.md")
    catalog_counts = _catalog_counts(root)
    gap = run_engine_universe_gap_analysis()
    benchmark = _classical_benchmark(root)
    module_status = build_module_statuses(repo_root=str(root))
    best_bacc = _readme_metric(r"retained holdout balanced accuracy:\s*([0-9.]+)", readme, 0.557273)
    retained_coverage = _readme_metric(r"retained forecast coverage:\s*([0-9.]+)", readme, 0.208926)
    expanded_bacc = _readme_metric(r"retained balanced accuracy:\s*([0-9.]+)", readme, 0.563179)
    expanded_rows = _readme_metric(r"retained fresh-holdout rows:\s*([0-9,]+)", readme, 205)
    expanded_coverage = _readme_metric(r"retained coverage:\s*([0-9.]+)", readme, 0.006905)
    tests_passed = _readme_metric(r"(\d+)\s+passed", readme, 804)

    return {
        "product_status": {
            "name": "Vietcombank Stock Evaluation Framework",
            "short_name": "VSEF",
            "subtitle": "AI-assisted diagnostic workspace for evidence-based banking stock evaluation.",
            "status": "full local proposal UI prototype",
            "scope": "research-only diagnostic workspace",
            "local_only": True,
            "live_data": False,
            "provider_calls": False,
            "cloud_calls": False,
            "trading_output": False,
            "human_review_required": True,
            "tests_passed_documented": tests_passed,
        },
        "architecture_modules": module_status["modules"],
        "engine_universe": {
            "generated_specs": catalog_counts["total"],
            "baseline_specs": catalog_counts["baseline"],
            "auxiliary_specs": catalog_counts["auxiliary"],
            "stack_specs": catalog_counts["stack"],
            "static_only_sweep": {
                "discovered": gap.get("total_specs_discovered", 77_850),
                "attempted": gap.get("total_specs_attempted", 77_850),
                "completed": gap.get("completed_count", 120),
                "skipped": gap.get("skipped_count", 77_730),
                "failed": gap.get("failed_count", 0),
            },
            "generated_evidence_sweep": {
                "discovered": 77_850,
                "attempted": 77_850,
                "completed": 9_960,
                "skipped": 67_890,
                "failed": 0,
                "source_status": "documented demo evidence lane",
            },
            "top_skip_reasons": gap.get("skip_reason_distribution", {}),
            "important_note": "77,850 means generated diagnostic engine specs, not 77,850 trained models.",
        },
        "forecast_accuracy_gate": {
            "current_broad_local_gate": {
                "best_release_candidate_bacc_percent": round(float(best_bacc) * 100, 4),
                "coverage_percent": round(float(retained_coverage) * 100, 4),
                "gap_to_60_percentage_points": round(60.0 - (float(best_bacc) * 100), 4),
                "release_status": STATUS_BLOCKED_BELOW,
                "broad_performance_claim_allowed": False,
            },
            "data_expanded_attempt": {
                "retained_bacc_percent": round(float(expanded_bacc) * 100, 4),
                "rows": int(expanded_rows),
                "coverage_percent": round(float(expanded_coverage) * 100, 4),
                "status": STATUS_BLOCKED_ROWS,
                "expanded_data_available": False,
                "ohlcv_only_fallback_blocked": True,
                "broad_performance_claim_allowed": False,
            },
            "message": "The system blocks forecast-performance claims when the 60% release gate is not met.",
            "human_review_required": True,
        },
        "classical_61pct_benchmark": benchmark,
        "data_expansion_requirement": {
            "status": "real expanded data required",
            "required_sources": [
                "OHLCV",
                "adjusted close",
                "turnover",
                "market cap",
                "foreign flow",
                "VNINDEX/VN30 index context",
                "sector/industry context",
                "news/social/event context",
            ],
            "provider_fetch": "disabled by default",
            "live_data_gateway": "later scope",
        },
        "risk_management": {
            "risk_categories": [
                "Data quality risk",
                "Liquidity risk",
                "Volatility/gap risk",
                "Model disagreement risk",
                "Calibration risk",
                "Leakage/duplicate/overlap risk",
                "Evidence staleness risk",
                "Claim-boundary risk",
            ],
            "review_status": "human review required",
            "no_portfolio_allocation_advice": True,
        },
        "social_listening_placeholder": {
            "status": "contract only / later integration",
            "demo_placeholder": True,
            "no_scraping": True,
            "no_live_api": True,
            "no_unverified_sentiment_claim": True,
            "sample_cards": [
                "Banking sector policy context",
                "Interest rate discussion",
                "Credit growth narrative",
                "Market liquidity conditions",
            ],
        },
        "rag_llm_placeholder": {
            "status": "static demo, no real LLM call",
            "retrieves_local_evidence_summaries": True,
            "cannot_mutate_models": True,
            "cannot_output_market_actions": True,
            "optional_local_ollama": "separate optional local-only module if installed",
        },
        "human_review": {
            "required": True,
            "review_items": [
                "Forecast claim review",
                "Data quality review",
                "61.61% benchmark scope review",
                "60% gate failure review",
                "Engine-universe skip reason review",
                "Expanded data requirement review",
            ],
            "allowed_actions": [
                "approve diagnostic wording",
                "request more data",
                "reject broad claim",
                "mark evidence insufficient",
                "export report",
            ],
        },
        "report_builder": {
            "status": "preview-only local report builder",
            "sections": [
                "Executive Summary",
                "Architecture",
                "Data Sources",
                "Engine Universe",
                "Forecast Accuracy Evidence",
                "61.61% Benchmark Lane",
                "60% Gate Status",
                "Risk Review",
                "Human Review Notes",
                "Claim Boundaries",
            ],
            "output_root": ".tmp_web_ui_demo",
            "writes_by_default": False,
        },
        "safe_demo_commands": [
            "python -m src.hackaithon_mvp.web_ui.app --host 127.0.0.1 --port 8765",
            "python -m src.hackaithon_mvp.final_claim_boundary_audit --format report",
        ],
        "blocked_claims": [
            "Broad system-wide 61% accuracy claim",
            "Production deployment claim",
            "Operational recommendation",
            "Profitability claim",
            "All-stocks forecast-performance claim",
        ],
    }


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_strings(item)


def validate_proposal_ui_summary(summary: dict) -> dict:
    """Validate required sections and local-only safety flags for the UI summary."""

    missing = [section for section in REQUIRED_SUMMARY_SECTIONS if section not in summary]
    product = summary.get("product_status") if isinstance(summary.get("product_status"), dict) else {}
    errors = []
    if missing:
        errors.extend(f"missing section: {section}" for section in missing)
    expected_flags = {
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "trading_output": False,
        "human_review_required": True,
    }
    for key, expected in expected_flags.items():
        if product.get(key) is not expected:
            errors.append(f"product_status.{key} must be {expected}")
    text = "\n".join(_walk_strings(summary))
    for forbidden in FORBIDDEN_PUBLIC_OUTPUT:
        if forbidden in text:
            errors.append(f"forbidden public output text present: {forbidden}")
    if "VSEF predicts stocks with 61" in text:
        errors.append("broad 61 percent system accuracy wording is not allowed")
    return {
        "validation_status": "valid" if not errors else "invalid",
        "valid": not errors,
        "missing_sections": missing,
        "errors": errors,
        "local_only": product.get("local_only") is True,
        "live_data": product.get("live_data") is True,
        "provider_calls": product.get("provider_calls") is True,
        "human_review_required": product.get("human_review_required") is True,
    }
