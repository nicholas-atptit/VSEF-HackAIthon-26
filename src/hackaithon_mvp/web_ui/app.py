"""FastAPI app for the local VSEF terminal web UI prototype."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.hackaithon_mvp.web_ui.data_provider import (
    build_demo_stock_profile,
    build_module_statuses,
    build_proposal_ui_summary,
    build_report_preview,
    build_terminal_command_response,
    build_ticker_terminal_profile,
    build_vn30_terminal_universe,
)


PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
REPO_ROOT = Path(__file__).resolve().parents[3]


def create_app(*, repo_root: str | Path = REPO_ROOT) -> FastAPI:
    """Create the local-only terminal web UI app."""

    app = FastAPI(
        title="VSEF Terminal Local Web UI Prototype",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "local_only": True,
            "live_data": False,
            "provider_calls": False,
            "trading_output": False,
            "human_review_required": True,
        }

    @app.get("/api/summary")
    def summary() -> JSONResponse:
        return JSONResponse(build_proposal_ui_summary(repo_root=str(repo_root)))

    @app.get("/api/proposal-flow")
    def proposal_flow() -> dict:
        return {
            "flow": [
                "Raw Local Files",
                "Schema Validation",
                "Feature Builder",
                "Forecast Rows",
                "Evidence Store",
                "Review UI",
            ],
            "local_only": True,
            "provider_calls": False,
            "human_review_required": True,
        }

    @app.get("/api/modules")
    def modules() -> JSONResponse:
        return JSONResponse(build_module_statuses(repo_root=str(repo_root)))

    @app.get("/api/vn30")
    def vn30() -> JSONResponse:
        return JSONResponse(build_vn30_terminal_universe(repo_root=str(repo_root)))

    @app.get("/api/ticker/{ticker}")
    def ticker_profile(ticker: str) -> JSONResponse:
        return JSONResponse(build_ticker_terminal_profile(ticker=ticker, repo_root=str(repo_root)))

    @app.get("/api/terminal-command")
    def terminal_command(cmd: str = "HELP") -> JSONResponse:
        return JSONResponse(build_terminal_command_response(command=cmd, repo_root=str(repo_root)))

    @app.get("/api/report-preview")
    def report_preview(ticker: str = "VCB") -> JSONResponse:
        return JSONResponse(build_report_preview(ticker=ticker, repo_root=str(repo_root)))

    @app.get("/api/demo-stock")
    def demo_stock(ticker: str = "VCB") -> JSONResponse:
        return JSONResponse(build_demo_stock_profile(ticker=ticker))

    @app.exception_handler(404)
    def not_found(_, __) -> JSONResponse:
        raise HTTPException(status_code=404, detail="local UI route not found")

    return app


app = create_app()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local VSEF terminal web UI prototype.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    uvicorn.run(
        "src.hackaithon_mvp.web_ui.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
