"""Local forecast-actual evaluation loop with optional storage persistence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.actual_outcome_builder import (
    OPTIONAL_FORECAST_FIELDS,
    build_actual_outcomes,
    load_local_rows,
)
from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.local_storage import parquet_adapter
from src.hackaithon_mvp.local_storage.storage_paths import build_partition_path
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


CLAIM_BOUNDARY = {
    "local_rows_only": True,
    "storage_write_default": False,
    "server_database_created": False,
    "data_gateway_created": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_enabled": False,
    "inference_enabled": False,
    "benchmark_rerun": False,
    "missing_actuals_are_skipped": True,
}
NON_CLAIM_TEXT = "Local diagnostic loop only; actual outcomes require provided local bars."
SOURCE_LOOP = "forecast_actual_dag_loop"
CREATED_AT_FALLBACK = "1970-01-01T00:00:00+00:00"
EVALUATION_FIELDS = (
    "actual_data_status",
    "rows_total",
    "eligible_directional_rows",
    "abstained_rows",
    "correct_directional_rows",
    "incorrect_directional_rows",
    "directional_accuracy",
    "balanced_directional_accuracy",
    "coverage_ratio",
    "abstention_ratio",
    "top_k_summary",
    "warnings",
)


def _empty_storage_write_summary(storage_root: str | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "storage_write_enabled": False,
        "records_written": 0,
        "write_results": {},
        "storage_format": None,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }
    if storage_root:
        summary["storage_root"] = str(storage_root).replace("\\", "/")
    return summary


def _date_from_timestamp(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return None


def _unique_value(rows: tuple[dict, ...], field: str) -> str | None:
    values = {str(row[field]).strip() for row in rows if row.get(field) not in (None, "")}
    return next(iter(values)) if len(values) == 1 else None


def _partition_kwargs(
    rows: tuple[dict, ...],
    *,
    ticker: str | None = None,
    timeframe: str | None = None,
    date: str | None = None,
) -> dict[str, str]:
    if not rows:
        return {}
    partition_ticker = str(ticker).strip().upper() if ticker else _unique_value(rows, "ticker")
    partition_timeframe = normalize_timeframe(timeframe) if timeframe else _unique_value(rows, "timeframe")
    dates = {
        value
        for value in (_date_from_timestamp(row.get("prediction_timestamp")) for row in rows)
        if value is not None
    }
    partition_date = date or (next(iter(dates)) if len(dates) == 1 else None)

    kwargs: dict[str, str] = {}
    if partition_ticker:
        kwargs["ticker"] = partition_ticker
    if partition_timeframe:
        kwargs["timeframe"] = partition_timeframe
    if partition_date:
        kwargs["date"] = partition_date
    return kwargs


def _read_market_bars_from_storage(
    *,
    storage_root: str,
    ticker: str,
    timeframe: str,
    date: str | None = None,
) -> tuple[dict, ...]:
    normalized_ticker = str(ticker).strip().upper()
    normalized_timeframe = normalize_timeframe(timeframe)
    if date is not None:
        return parquet_adapter.read_dataset_records(
            storage_root,
            "market_bars",
            ticker=normalized_ticker,
            timeframe=normalized_timeframe,
            date=date,
        )

    base = Path(
        build_partition_path(
            storage_root,
            "market_bars",
            ticker=normalized_ticker,
            timeframe=normalized_timeframe,
        )
    )
    if not base.exists():
        return ()
    records: list[dict[str, Any]] = []
    for partition in sorted(base.glob("date=*")):
        if partition.is_dir():
            records.extend(parquet_adapter.read_records(str(partition / "part.parquet")))
    if records:
        return tuple(records)
    return parquet_adapter.read_dataset_records(
        storage_root,
        "market_bars",
        ticker=normalized_ticker,
        timeframe=normalized_timeframe,
    )


def build_actual_outcome_storage_records(rows: tuple[dict, ...]) -> tuple[dict, ...]:
    """Build compact local-storage records for forecast-actual outcome rows."""

    records: list[dict[str, Any]] = []
    required_fields = (
        "ticker",
        "timeframe",
        "prediction_timestamp",
        "actual_timestamp",
        "horizon_steps",
        "forecast_diagnostic",
        "actual_future_return",
        "actual_direction_label",
    )
    for row in rows:
        record = {field: row.get(field) for field in required_fields}
        for field in OPTIONAL_FORECAST_FIELDS:
            if row.get(field) not in (None, ""):
                record[field] = row[field]
        record["source_loop"] = SOURCE_LOOP
        records.append(record)
    return tuple(records)


def _compact_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    compact = {field: evaluation.get(field) for field in EVALUATION_FIELDS if field in evaluation}
    compact["claim_boundary"] = dict(CLAIM_BOUNDARY)
    compact["non_claim"] = NON_CLAIM_TEXT
    return compact


def build_evaluation_metric_record(evaluation: dict, *, run_id: str | None = None) -> dict:
    """Build one compact evaluation metric storage record."""

    return {
        "run_id": run_id,
        "rows_total": int(evaluation.get("rows_total") or 0),
        "eligible_directional_rows": int(evaluation.get("eligible_directional_rows") or 0),
        "abstained_rows": int(evaluation.get("abstained_rows") or 0),
        "correct_directional_rows": int(evaluation.get("correct_directional_rows") or 0),
        "incorrect_directional_rows": int(evaluation.get("incorrect_directional_rows") or 0),
        "directional_accuracy": evaluation.get("directional_accuracy"),
        "balanced_directional_accuracy": evaluation.get("balanced_directional_accuracy"),
        "coverage_ratio": evaluation.get("coverage_ratio"),
        "abstention_ratio": evaluation.get("abstention_ratio"),
        "top_k_summary": evaluation.get("top_k_summary"),
        "created_at": evaluation.get("created_at", CREATED_AT_FALLBACK),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _combined_storage_format(write_results: dict[str, dict[str, Any]]) -> str | None:
    formats = {
        str(result.get("storage_format"))
        for result in write_results.values()
        if isinstance(result, dict) and result.get("storage_format")
    }
    if not formats:
        return None
    if len(formats) == 1:
        return next(iter(formats))
    return "mixed"


def _persist_loop_records(
    *,
    storage_root: str,
    actual_rows: tuple[dict, ...],
    evaluation: dict[str, Any],
    ticker: str | None = None,
    timeframe: str | None = None,
    date: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    metric_run_id = run_id or _deterministic_run_id(actual_rows, evaluation)
    write_results: dict[str, dict[str, Any]] = {}
    records_written = 0

    actual_records = build_actual_outcome_storage_records(actual_rows)
    if actual_records:
        result = parquet_adapter.write_dataset_records(
            storage_root,
            "actual_outcomes",
            actual_records,
            **_partition_kwargs(actual_records, ticker=ticker, timeframe=timeframe, date=date),
        )
        write_results["actual_outcomes"] = result
        records_written += int(result.get("row_count", 0))

    metric_record = build_evaluation_metric_record(evaluation, run_id=metric_run_id)
    result = parquet_adapter.write_dataset_records(
        storage_root,
        "evaluation_metrics",
        (metric_record,),
        run_id=metric_run_id,
    )
    write_results["evaluation_metrics"] = result
    records_written += int(result.get("row_count", 0))

    return {
        "storage_write_enabled": True,
        "storage_root": str(storage_root).replace("\\", "/"),
        "records_written": records_written,
        "write_results": write_results,
        "storage_format": _combined_storage_format(write_results),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _deterministic_run_id(actual_rows: tuple[dict, ...], evaluation: dict[str, Any]) -> str:
    payload = {
        "row_count": len(actual_rows),
        "first_prediction_timestamp": actual_rows[0].get("prediction_timestamp") if actual_rows else None,
        "rows_total": evaluation.get("rows_total"),
        "directional_accuracy": evaluation.get("directional_accuracy"),
        "coverage_ratio": evaluation.get("coverage_ratio"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return f"forecast_actual_loop_{digest}"


def run_forecast_actual_loop(
    *,
    forecast_rows: tuple[dict, ...],
    bar_rows: tuple[dict, ...] | None = None,
    storage_root: str | None = None,
    ticker: str | None = None,
    timeframe: str | None = None,
    date: str | None = None,
    match_mode: str = "exact",
    top_k: int | None = None,
    persist: bool = False,
) -> dict:
    """Run the local forecast-actual loop with optional local persistence."""

    if not isinstance(forecast_rows, tuple):
        raise ValueError("forecast_rows must be a tuple of dictionaries")
    if not all(isinstance(row, dict) for row in forecast_rows):
        raise ValueError("forecast_rows must contain dictionaries only")
    if top_k is not None and int(top_k) <= 0:
        raise ValueError("top_k must be positive when provided")
    if persist and not storage_root:
        raise ValueError("storage_root is required when persist is true")

    loaded_bars: tuple[dict, ...]
    storage_context = "not_requested"
    if bar_rows is not None:
        if not isinstance(bar_rows, tuple) or not all(isinstance(row, dict) for row in bar_rows):
            raise ValueError("bar_rows must be a tuple of dictionaries when provided")
        loaded_bars = bar_rows
        storage_context = "not_used"
    elif storage_root:
        if not ticker or not timeframe:
            raise ValueError("ticker and timeframe are required when loading bars from storage")
        loaded_bars = _read_market_bars_from_storage(
            storage_root=storage_root,
            ticker=ticker,
            timeframe=timeframe,
            date=date,
        )
        storage_context = "provided" if loaded_bars else "missing"
    else:
        loaded_bars = ()

    if not loaded_bars:
        return {
            "loop_status": "missing_bars",
            "actual_outcome_status": "missing_bars",
            "evaluation_status": "not_run",
            "forecast_rows_total": len(forecast_rows),
            "actual_outcome_rows": 0,
            "skipped_forecast_rows": len(forecast_rows),
            "evaluation": {},
            "storage_context_status": storage_context,
            "storage_write_enabled": False,
            "storage_write_summary": _empty_storage_write_summary(storage_root),
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    actual_rows = build_actual_outcomes(forecast_rows, loaded_bars, match_mode=match_mode)
    evaluation = evaluate_forecast_vs_actual(actual_rows, top_k=top_k)
    storage_write_summary = _empty_storage_write_summary(storage_root)
    if persist:
        storage_write_summary = _persist_loop_records(
            storage_root=str(storage_root),
            actual_rows=actual_rows,
            evaluation=evaluation,
            ticker=ticker,
            timeframe=timeframe,
            date=date,
        )

    return {
        "loop_status": "completed",
        "actual_outcome_status": "provided" if actual_rows else "skipped",
        "evaluation_status": "completed",
        "forecast_rows_total": len(forecast_rows),
        "actual_outcome_rows": len(actual_rows),
        "skipped_forecast_rows": max(0, len(forecast_rows) - len(actual_rows)),
        "evaluation": _compact_evaluation(evaluation),
        "storage_context_status": storage_context,
        "storage_write_enabled": bool(persist),
        "storage_write_summary": storage_write_summary,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def attach_evaluation_to_dag_result(
    dag_result: dict,
    evaluation: dict,
) -> dict:
    """Attach compact forecast-actual evaluation metadata to a DAG result copy."""

    updated = copy.deepcopy(dag_result)
    compact = _compact_evaluation(evaluation)
    updated["forecast_actual_evaluation"] = compact
    final_state = updated.get("final_state")
    if isinstance(final_state, dict):
        final_state["forecast_actual_evaluation"] = compact
        final_state["actual_data_status"] = evaluation.get("actual_data_status")
        final_state["directional_accuracy"] = evaluation.get("directional_accuracy")
        final_state["balanced_directional_accuracy"] = evaluation.get("balanced_directional_accuracy")
        final_state["coverage_ratio"] = evaluation.get("coverage_ratio")
    return updated


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local forecast-actual diagnostic loop.")
    parser.add_argument("--forecasts", required=True)
    parser.add_argument("--bars", default=None)
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--match-mode", choices=("exact", "nearest_prior"), default="exact")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--format", choices=("json",), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.bars and not args.storage_root:
        parser.error("either --bars or --storage-root must be provided")
    if args.storage_root and not args.bars and (not args.ticker or not args.timeframe):
        parser.error("--ticker and --timeframe are required when reading bars from --storage-root")
    if args.persist and not args.storage_root:
        parser.error("--persist requires --storage-root")
    try:
        forecast_rows = load_local_rows(args.forecasts)
        bar_rows = load_local_rows(args.bars) if args.bars else None
        result = run_forecast_actual_loop(
            forecast_rows=forecast_rows,
            bar_rows=bar_rows,
            storage_root=args.storage_root,
            ticker=args.ticker,
            timeframe=args.timeframe,
            date=args.date,
            match_mode=args.match_mode,
            top_k=args.top_k,
            persist=bool(args.persist),
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
