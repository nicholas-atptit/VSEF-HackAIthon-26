"""Optional Vietnamese market data adapter contract, disabled by default."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


REQUIRED_ENV = ("DATA_PROVIDER", "START_DATE", "END_DATE", "MAX_TICKERS", "OUTPUT_ROOT")
CLAIM_BOUNDARY = {
    "disabled_by_default": True,
    "requires_explicit_env_flag": True,
    "does_not_print_secrets": True,
    "writes_only_under_approved_tmp_roots": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Optional provider adapter is a disabled data-expansion contract unless explicit environment flags are set."
ALLOWED_OUTPUT_ROOT_PREFIXES = (".tmp_data_expanded_60pct", ".tmp_real_expanded_60pct")


def _safe_output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(
        any(part.lower().startswith(prefix) for prefix in ALLOWED_OUTPUT_ROOT_PREFIXES)
        for part in root.parts
    ):
        raise ValueError("output_root must be .tmp_data_expanded_60pct, .tmp_real_expanded_60pct, or a child path")
    return root


def _safe_env_value(key: str, value: str | None) -> str | int | None:
    if value in (None, ""):
        return None
    if "SECRET" in key.upper() or "TOKEN" in key.upper() or "KEY" in key.upper() or "PASSWORD" in key.upper():
        return "set_redacted"
    if key == "MAX_TICKERS":
        try:
            return int(value)
        except ValueError:
            return value
    return value


def inspect_vn_market_data_config(*, output_root: str | Path | None = None) -> dict:
    """Inspect provider-expansion environment without exposing secrets."""

    configured_output = str(output_root or os.environ.get("OUTPUT_ROOT") or "")
    env = {key: _safe_env_value(key, os.environ.get(key)) for key in REQUIRED_ENV}
    if output_root is not None:
        env["OUTPUT_ROOT"] = str(output_root)
    enabled = os.environ.get("ALLOW_PROVIDER_DATA_FETCH") == "1"
    missing = [key for key in REQUIRED_ENV if not env.get(key)]
    return {
        "data_fetch_enabled": enabled,
        "allow_provider_data_fetch": "1" if enabled else "",
        "config": env,
        "missing_required_env": missing,
        "output_root": configured_output,
        "preferred_data_targets": [
            "VN30 tickers",
            "VNINDEX or VN30 index proxy",
            "adjusted OHLCV if available",
            "turnover or traded value if available",
            "foreign trading fields if available",
            "sector or industry proxy if available",
        ],
        "required_output_file": "expanded_price_panel.csv",
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _provider_available(provider: str | None) -> tuple[bool, str | None]:
    if str(provider or "").lower() != "vnstock":
        return False, "provider_not_configured"
    try:
        import vnstock  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - optional local dependency boundary.
        return False, f"provider_not_configured:{type(exc).__name__}"
    return False, "provider_connector_not_implemented"


def _provider_gaps(reason: str | None) -> list[str]:
    gaps = []
    if reason:
        gaps.append(str(reason))
    gaps.extend(
        [
            "vn30_ticker_panel_not_written",
            "index_proxy_fields_not_written",
            "adjusted_price_fields_not_confirmed",
            "turnover_or_value_fields_not_confirmed",
            "foreign_flow_fields_not_confirmed",
            "sector_or_industry_fields_not_confirmed",
        ]
    )
    return gaps


def run_optional_vn_market_data_expansion(*, output_root: str) -> dict:
    """Run optional provider expansion only when explicitly enabled and configured."""

    config = inspect_vn_market_data_config(output_root=output_root)
    if not config["data_fetch_enabled"]:
        return {
            **config,
            "data_expansion_status": "disabled",
            "written_files": [],
            "expanded_data_available": False,
            "provider_gaps": ["provider_fetch_disabled_by_default"],
        }
    if config["missing_required_env"]:
        return {
            **config,
            "data_expansion_status": "missing_required_env",
            "written_files": [],
            "expanded_data_available": False,
            "provider_gaps": ["missing_required_env"],
        }
    root = _safe_output_root(output_root)
    available, reason = _provider_available(str(config["config"].get("DATA_PROVIDER") or ""))
    if not available:
        root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "data_expansion_status": "provider_not_configured",
            "reason": reason,
            "config": config["config"],
            "preferred_data_targets": config["preferred_data_targets"],
            "provider_gaps": _provider_gaps(reason),
            "expanded_data_available": False,
        }
        (root / "data_expansion_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            **config,
            "data_expansion_status": "provider_not_configured",
            "provider_reason": reason,
            "written_files": [str(root / "data_expansion_manifest.json")],
            "expanded_data_available": False,
            "provider_gaps": _provider_gaps(reason),
        }
    # A connector can be added later behind the same explicit gate. Do not fabricate data here.
    root.mkdir(parents=True, exist_ok=True)
    reason = "connector_not_implemented"
    manifest = {
        "data_expansion_status": "provider_not_configured",
        "reason": reason,
        "config": config["config"],
        "preferred_data_targets": config["preferred_data_targets"],
        "provider_gaps": _provider_gaps(reason),
        "expanded_data_available": False,
    }
    (root / "data_expansion_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        **config,
        "data_expansion_status": "provider_not_configured",
        "provider_reason": reason,
        "written_files": [str(root / "data_expansion_manifest.json")],
        "expanded_data_available": False,
        "provider_gaps": _provider_gaps(reason),
    }


def render_optional_vn_market_data_report(result: dict) -> str:
    """Render provider adapter status without secrets."""

    lines = [
        "# Optional VN Market Data Adapter",
        "",
        f"Data expansion status: {result.get('data_expansion_status', 'config_inspected')}",
        f"Provider fetch enabled: {result.get('data_fetch_enabled')}",
        f"Missing required env: {result.get('missing_required_env') or []}",
        f"Output root: {result.get('output_root')}",
        f"Expanded data available: {result.get('expanded_data_available', False)}",
        f"Provider reason: {result.get('provider_reason')}",
        f"Provider gaps: {result.get('provider_gaps') or []}",
        "Preferred targets:",
    ]
    lines.extend([f"- {item}" for item in result.get("preferred_data_targets") or []] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Provider fetches are disabled unless ALLOW_PROVIDER_DATA_FETCH=1 and all required env values are set.",
            "No secrets are printed.",
            "Provider outputs, when available, must stay under the requested temporary data root.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optional VN market data adapter, disabled by default.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_optional_vn_market_data_expansion(output_root=args.output_root)
    if args.format == "report":
        print(render_optional_vn_market_data_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
