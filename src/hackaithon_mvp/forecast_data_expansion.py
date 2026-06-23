"""Optional local/provider data expansion contract for forecast-edge work."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


REQUIRED_ENABLED_ENV = ("DATA_PROVIDER", "MAX_TICKERS", "START_DATE", "END_DATE")
CLAIM_BOUNDARY = {
    "disabled_by_default": True,
    "requires_explicit_env_flag": True,
    "does_not_print_secrets": True,
    "writes_only_under_tmp_forecast_edge": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Data expansion is an explicit local contract; provider fetches are disabled unless configured."


def _redacted_env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    if "KEY" in name.upper() or "SECRET" in name.upper() or "TOKEN" in name.upper() or "PASSWORD" in name.upper():
        return "<redacted>"
    return str(value)


def _output_root(path: str | Path) -> Path:
    root = Path(path)
    if not any(part.lower().startswith(".tmp_forecast_edge") for part in root.parts):
        raise ValueError("output_root must be .tmp_forecast_edge or a child path")
    root.mkdir(parents=True, exist_ok=True)
    return root


def inspect_data_expansion_config() -> dict:
    """Inspect the explicit environment contract without reading or printing secrets."""

    enabled = os.environ.get("ALLOW_PROVIDER_DATA_FETCH") == "1"
    config = {
        "ALLOW_PROVIDER_DATA_FETCH": "1" if enabled else os.environ.get("ALLOW_PROVIDER_DATA_FETCH", ""),
        "DATA_PROVIDER": _redacted_env_value("DATA_PROVIDER"),
        "MAX_TICKERS": _redacted_env_value("MAX_TICKERS"),
        "START_DATE": _redacted_env_value("START_DATE"),
        "END_DATE": _redacted_env_value("END_DATE"),
    }
    if not enabled:
        status = "disabled_by_default"
        missing: list[str] = []
    else:
        missing = [name for name in REQUIRED_ENABLED_ENV if not os.environ.get(name)]
        status = "missing_required_config" if missing else "provider_not_configured"
    return {
        "data_expansion_status": status,
        "enabled": enabled,
        "missing_required_env": missing,
        "config": config,
        "provider_connector_available": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def run_optional_data_expansion(*, output_root: str) -> dict:
    """Run optional data expansion only when explicitly enabled and configured."""

    root = _output_root(output_root)
    config = inspect_data_expansion_config()
    status = config["data_expansion_status"]
    result: dict[str, Any] = {
        **config,
        "output_root": str(root),
        "written_files": [],
    }
    if status in {"disabled_by_default", "missing_required_config"}:
        return result
    result["data_expansion_status"] = "provider_not_configured"
    result["provider_connector_available"] = False
    return result


def render_data_expansion_report(result: dict) -> str:
    """Render the optional data-expansion contract."""

    lines = [
        "# Forecast Data Expansion Contract",
        "",
        f"Data expansion status: {result.get('data_expansion_status')}",
        f"Enabled: {result.get('enabled')}",
        f"Provider connector available: {result.get('provider_connector_available')}",
        f"Missing required env: {result.get('missing_required_env') or []}",
        f"Output root: {result.get('output_root', 'not requested')}",
        "",
        "Boundary:",
        "Provider fetch remains disabled unless ALLOW_PROVIDER_DATA_FETCH is exactly 1.",
        "Required provider values are inspected without exposing credential-like values.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or run optional forecast data expansion.")
    parser.add_argument("--output-root", default=".tmp_forecast_edge")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_optional_data_expansion(output_root=args.output_root)
    if args.format == "report":
        print(render_data_expansion_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
