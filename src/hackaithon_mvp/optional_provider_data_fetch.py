"""Explicitly gated provider data fetch contract for local full-run experiments."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


CLAIM_BOUNDARY = {
    "disabled_by_default": True,
    "requires_allow_provider_flag": True,
    "writes_files_by_default": False,
    "secrets_logged": False,
    "no_model_training": True,
    "no_live_inference": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Provider fetch contract only; no provider integration is active unless explicitly configured."


def _env_flag(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value is not None else None


def run_optional_provider_data_fetch(
    *,
    output_path: str | None = None,
    allow_provider_fetch: bool | None = None,
) -> dict:
    """Return disabled/provider-not-configured status unless explicit flags are set."""

    allow = allow_provider_fetch if allow_provider_fetch is not None else _env_flag("ALLOW_PROVIDER_DATA_FETCH") == "1"
    provider = _env_flag("DATA_PROVIDER")
    max_tickers = _env_flag("MAX_TICKERS")
    start_date = _env_flag("START_DATE")
    end_date = _env_flag("END_DATE")
    if not allow:
        status = "disabled_by_default"
        rows: list[dict] = []
    elif not provider:
        status = "provider_not_configured"
        rows = []
    else:
        status = "provider_integration_not_implemented"
        rows = []

    if output_path and rows:
        path = Path(output_path)
        if not any(part.lower().startswith(".tmp_full_model_run") for part in path.parts):
            raise ValueError("provider output path must be under .tmp_full_model_run")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")

    return {
        "provider_fetch_status": status,
        "provider": provider,
        "max_tickers": max_tickers,
        "start_date": start_date,
        "end_date": end_date,
        "row_count": len(rows),
        "output_path": output_path if rows else None,
        "secrets_logged": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_optional_provider_data_fetch_report(result: dict) -> str:
    """Render a compact provider-fetch contract report."""

    lines = [
        "# Optional Provider Data Fetch",
        "",
        f"Provider fetch status: {result.get('provider_fetch_status')}",
        f"Provider: {result.get('provider') or 'not_configured'}",
        f"Ticker cap: {result.get('max_tickers') or 'not_configured'}",
        f"Date range: {result.get('start_date') or 'not_configured'} to {result.get('end_date') or 'not_configured'}",
        f"Rows fetched: {result.get('row_count')}",
        "",
        "Boundary:",
        "Disabled unless ALLOW_PROVIDER_DATA_FETCH=1 and a provider contract is configured.",
        "No secrets are printed, and fetched data would require explicit .tmp_full_model_run output.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check optional provider fetch configuration.")
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_optional_provider_data_fetch(output_path=args.output_path)
    if args.format == "report":
        print(render_optional_provider_data_fetch_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
