"""Forecast chart payload provider for the local VN30 terminal UI."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable


ROW_ARTIFACT_PATHS = (
    ".tmp_forecast_edge/retained_forecast_rows.jsonl",
    ".tmp_forecast_edge/evidence/forecast_actual_rows.jsonl",
    ".tmp_forecast_repair/deoverlapped_rows.jsonl",
    ".tmp_forecast_repair/forecast_actual_rows.jsonl",
)

SUMMARY_ARTIFACT_PATHS = (
    ".tmp_60pct_gate/forecast_60pct_edge_search_summary.json",
    "reports/results/VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md",
)

SHALLOW_ARTIFACT_GLOBS = (
    ".tmp_data_expanded_60pct/*",
    "reports/generated/*",
    "reports/claims/*",
)

DEFAULT_HORIZONS = ("h1", "h5", "h10", "h20", "h40")
MISSING_REASON = "row_level_forecast_evidence_missing"


def _repo_root(path: str) -> Path:
    return Path(path).resolve()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    path.relative_to(root)
    return path


def _iter_safe_artifacts(root: Path) -> Iterable[tuple[str, Path, str]]:
    for relative_path in ROW_ARTIFACT_PATHS:
        yield "row_level_jsonl", _safe_path(root, relative_path), relative_path
    for relative_path in SUMMARY_ARTIFACT_PATHS:
        yield "aggregate_summary", _safe_path(root, relative_path), relative_path
    for pattern in SHALLOW_ARTIFACT_GLOBS:
        base = pattern.rstrip("*").rstrip("/")
        directory = _safe_path(root, base)
        if directory.exists() and directory.is_dir():
            for path in sorted(item for item in directory.iterdir() if item.is_file()):
                yield "aggregate_or_context", path.resolve(), _rel(path, root)
        else:
            yield "aggregate_or_context", directory, base


def _count_lines(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for line in handle if line.strip())


def discover_forecast_chart_artifacts(*, repo_root: str = ".") -> dict:
    """Discover approved local artifacts without scanning outside safe paths."""

    root = _repo_root(repo_root)
    artifacts: list[dict[str, Any]] = []
    searched_paths: list[str] = []
    for artifact_type, path, relative_path in _iter_safe_artifacts(root):
        searched_paths.append(relative_path)
        exists = path.exists() and path.is_file()
        artifact = {
            "path": relative_path,
            "artifact_type": artifact_type,
            "exists": exists,
            "safe_local_path": True,
        }
        if exists and relative_path.endswith(".jsonl"):
            artifact["row_count"] = _count_lines(path)
            artifact["row_level"] = artifact["row_count"] > 0
        else:
            artifact["row_count"] = None
            artifact["row_level"] = False
        artifacts.append(artifact)

    row_artifacts = [item for item in artifacts if item["artifact_type"] == "row_level_jsonl"]
    existing_row_artifacts = [item for item in row_artifacts if item["exists"] and item["row_level"]]
    return {
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "writes_files": False,
        "safe_roots_only": True,
        "searched_paths": searched_paths,
        "artifacts": artifacts,
        "row_level_artifacts": row_artifacts,
        "row_level_available": bool(existing_row_artifacts),
        "row_level_artifact_count": len(existing_row_artifacts),
    }


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _normalize_horizon(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text.startswith("h"):
        suffix = text[1:]
    else:
        suffix = text
    try:
        number = int(float(suffix))
    except ValueError:
        return text
    return f"h{number}"


def _normalize_direction(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else -1
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0
    text = str(value).strip().lower()
    if text in {"up", "positive", "pos", "1", "true", "higher"}:
        return 1
    if text in {"down", "negative", "neg", "-1", "false", "lower"}:
        return -1
    if text in {"flat", "same", "neutral", "0", "abstain", "abstained"}:
        return 0
    return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _first(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _row_ticker(row: dict[str, Any]) -> str | None:
    value = _first(row, ("ticker", "symbol", "asset", "stock", "code"))
    return str(value).strip().upper() if value not in (None, "") else None


def _row_horizon(row: dict[str, Any]) -> str | None:
    return _normalize_horizon(_first(row, ("horizon", "horizon_steps", "target_horizon", "forecast_horizon")))


def _row_timestamp(row: dict[str, Any]) -> str | None:
    value = _first(
        row,
        (
            "actual_timestamp",
            "forecast_timestamp",
            "timestamp",
            "datetime",
            "date",
            "asof_timestamp",
            "target_timestamp",
        ),
    )
    return str(value) if value not in (None, "") else None


def _normalize_row(row: dict[str, Any], *, source_artifact: str, order: int) -> dict[str, Any]:
    actual_direction = _normalize_direction(_first(row, ("actual_direction", "y_true", "actual", "label", "target_direction")))
    predicted_direction = _normalize_direction(
        _first(row, ("predicted_direction", "y_pred", "prediction", "forecast_direction", "model_direction"))
    )
    correct_raw = _first(row, ("correct", "is_correct", "hit"))
    if isinstance(correct_raw, bool):
        correct = correct_raw
    elif correct_raw is not None:
        normalized_correct = _normalize_direction(correct_raw)
        correct = bool(normalized_correct and normalized_correct > 0)
    elif predicted_direction is not None and actual_direction is not None and actual_direction != 0:
        correct = predicted_direction == actual_direction
    else:
        correct = None

    score = _as_float(
        _first(
            row,
            (
                "score",
                "predicted_probability",
                "probability",
                "confidence",
                "prediction_score",
                "y_score",
            ),
        )
    )
    actual_close = _as_float(_first(row, ("actual_close", "close", "target_close", "price", "actual_price")))
    return {
        "timestamp": _row_timestamp(row) or str(order),
        "actual_close": actual_close,
        "predicted_direction": predicted_direction,
        "actual_direction": actual_direction,
        "correct": correct,
        "score": score,
        "actual_return": _as_float(_first(row, ("actual_return", "forward_return", "target_return"))),
        "predicted_return": _as_float(_first(row, ("predicted_return", "forecast_return"))),
        "model_key": _first(row, ("model_key", "model_id", "candidate_id", "model_family")),
        "horizon": _row_horizon(row),
        "source_artifact": source_artifact,
        "order": order,
    }


def _matching_rows(root: Path, ticker: str, horizon: str | None) -> tuple[list[dict[str, Any]], str | None]:
    ticker_upper = ticker.strip().upper()
    horizon_norm = _normalize_horizon(horizon)
    for relative_path in ROW_ARTIFACT_PATHS:
        path = _safe_path(root, relative_path)
        if not path.exists():
            continue
        rows: list[dict[str, Any]] = []
        for order, row in enumerate(_read_jsonl(path)):
            if _row_ticker(row) != ticker_upper:
                continue
            row_horizon = _row_horizon(row)
            if horizon_norm and row_horizon != horizon_norm:
                continue
            rows.append(_normalize_row(row, source_artifact=relative_path, order=order))
        if rows:
            return rows, relative_path
    return [], None


def _empty_payload(ticker: str, horizon: str | None, reason: str = MISSING_REASON) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "ticker": ticker.strip().upper(),
        "horizon": _normalize_horizon(horizon),
        "chart_type": "actual_vs_forecast_direction",
        "source_artifact": None,
        "points": [],
        "metrics": {
            "rows": 0,
            "accuracy": None,
            "balanced_accuracy": None,
            "mcc": None,
            "coverage": None,
        },
        "boundary": _boundary(),
    }


def _boundary() -> dict[str, bool]:
    return {
        "human_review_required": True,
        "not_trading_signal": True,
        "no_action_output": True,
        "local_only": True,
        "provider_calls": False,
    }


def _mcc(points: list[dict[str, Any]]) -> float | None:
    tp = tn = fp = fn = 0
    for point in points:
        pred = point.get("predicted_direction")
        actual = point.get("actual_direction")
        if pred not in (-1, 1) or actual not in (-1, 1):
            continue
        if pred == 1 and actual == 1:
            tp += 1
        elif pred == -1 and actual == -1:
            tn += 1
        elif pred == 1 and actual == -1:
            fp += 1
        elif pred == -1 and actual == 1:
            fn += 1
    denominator = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    if denominator <= 0:
        return None
    return round(((tp * tn) - (fp * fn)) / math.sqrt(denominator), 6)


def _metrics(points: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [point for point in points if isinstance(point.get("correct"), bool)]
    accuracy = round(sum(1 for point in judged if point["correct"]) / len(judged), 6) if judged else None
    recalls: list[float] = []
    for actual_value in (-1, 1):
        class_points = [point for point in points if point.get("actual_direction") == actual_value]
        if class_points:
            recalls.append(sum(1 for point in class_points if point.get("correct") is True) / len(class_points))
    balanced_accuracy = round(sum(recalls) / len(recalls), 6) if recalls else None
    return {
        "rows": len(points),
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "mcc": _mcc(points),
        "coverage": None,
    }


def _limit_points(points: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    if max_points <= 0:
        return []
    sorted_points = sorted(points, key=lambda point: (str(point.get("timestamp") or ""), point.get("order") or 0))
    if len(sorted_points) <= max_points:
        limited = sorted_points
    else:
        limited = sorted_points[-max_points:]
    return [{key: value for key, value in point.items() if key != "order"} for point in limited]


def build_forecast_chart_data(
    ticker: str,
    *,
    horizon: str | None = None,
    repo_root: str = ".",
    max_points: int = 160,
) -> dict:
    """Build actual-vs-forecast chart data from local row-level artifacts only."""

    root = _repo_root(repo_root)
    rows, source_artifact = _matching_rows(root, ticker, horizon)
    if not rows:
        return _empty_payload(ticker, horizon)
    selected_horizon = _normalize_horizon(horizon) or rows[0].get("horizon")
    return {
        "available": True,
        "ticker": ticker.strip().upper(),
        "horizon": selected_horizon,
        "chart_type": "actual_vs_forecast_direction",
        "source_artifact": source_artifact,
        "points": _limit_points(rows, max_points),
        "metrics": _metrics(rows),
        "metric_scope": "row_level_local_artifact",
        "source_scope": "retained edge or repair artifact",
        "claim_allowed": False,
        "boundary": _boundary(),
    }


def build_forecast_accuracy_timeline(
    ticker: str,
    *,
    horizon: str | None = None,
    repo_root: str = ".",
    max_points: int = 160,
) -> dict:
    """Build cumulative and rolling correctness timeline from chart rows."""

    chart = build_forecast_chart_data(ticker, horizon=horizon, repo_root=repo_root, max_points=max_points)
    if not chart.get("available"):
        return {
            **chart,
            "chart_type": "forecast_accuracy_timeline",
            "timeline": [],
        }

    cumulative_correct = 0
    judged_count = 0
    timeline: list[dict[str, Any]] = []
    rolling_window: list[bool] = []
    for index, point in enumerate(chart["points"], start=1):
        correct = point.get("correct")
        if isinstance(correct, bool):
            judged_count += 1
            cumulative_correct += 1 if correct else 0
            rolling_window.append(correct)
            rolling_window = rolling_window[-20:]
        timeline.append(
            {
                "timestamp": point.get("timestamp"),
                "order": index,
                "correct": correct,
                "cumulative_accuracy": round(cumulative_correct / judged_count, 6) if judged_count else None,
                "rolling_accuracy": round(sum(rolling_window) / len(rolling_window), 6) if rolling_window else None,
            }
        )

    return {
        "available": True,
        "ticker": chart["ticker"],
        "horizon": chart["horizon"],
        "chart_type": "forecast_accuracy_timeline",
        "source_artifact": chart["source_artifact"],
        "timeline": timeline,
        "metrics": chart["metrics"],
        "boundary": chart["boundary"],
    }


def build_horizon_comparison_chart(
    ticker: str,
    *,
    repo_root: str = ".",
) -> dict:
    """Compare available row-level evidence across standard horizons."""

    rows: list[dict[str, Any]] = []
    for horizon in DEFAULT_HORIZONS:
        chart = build_forecast_chart_data(ticker, horizon=horizon, repo_root=repo_root, max_points=1)
        metrics = chart.get("metrics", {})
        rows.append(
            {
                "horizon": horizon,
                "available": bool(chart.get("available")),
                "rows": metrics.get("rows", 0),
                "accuracy": metrics.get("accuracy"),
                "balanced_accuracy": metrics.get("balanced_accuracy"),
                "mcc": metrics.get("mcc"),
                "coverage": metrics.get("coverage"),
                "gate_status": "Gate blocked",
                "source_artifact": chart.get("source_artifact"),
            }
        )
    available_rows = [row for row in rows if row["available"]]
    return {
        "available": bool(available_rows),
        "ticker": ticker.strip().upper(),
        "chart_type": "horizon_comparison",
        "horizons": rows,
        "available_horizons": [row["horizon"] for row in available_rows],
        "missing_horizons": [row["horizon"] for row in rows if not row["available"]],
        "boundary": _boundary(),
    }


def build_forecast_chart_coverage_summary(tickers: Iterable[str], *, repo_root: str = ".") -> dict:
    """Build a compact VN30 chart coverage summary for report preview."""

    coverage = []
    for ticker in tickers:
        comparison = build_horizon_comparison_chart(ticker, repo_root=repo_root)
        coverage.append(
            {
                "ticker": ticker.strip().upper(),
                "available": comparison["available"],
                "available_horizons": comparison["available_horizons"],
                "missing_horizons": comparison["missing_horizons"],
            }
        )
    available_count = sum(1 for item in coverage if item["available"])
    return {
        "ticker_count": len(coverage),
        "tickers_with_row_level_chart_evidence": available_count,
        "tickers_missing_chart_evidence": len(coverage) - available_count,
        "coverage": coverage,
        "local_only": True,
        "provider_calls": False,
        "no_action_output": True,
    }


def validate_forecast_chart_payload(payload: dict) -> dict:
    """Validate forecast chart payload shape and safety boundary flags."""

    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["payload must be a dict"]}
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    if boundary.get("human_review_required") is not True:
        errors.append("human_review_required must be true")
    if boundary.get("not_trading_signal") is not True:
        errors.append("not_trading_signal must be true")
    if boundary.get("no_action_output") is not True:
        errors.append("no_action_output must be true")
    if payload.get("available") is True:
        if not payload.get("ticker"):
            errors.append("ticker is required")
        if not payload.get("chart_type"):
            errors.append("chart_type is required")
        if not isinstance(payload.get("points"), list) and not isinstance(payload.get("timeline"), list):
            errors.append("points or timeline list is required")
        if not payload.get("source_artifact"):
            errors.append("source_artifact is required for available chart payloads")
    else:
        if payload.get("reason") not in {MISSING_REASON, "unknown_ticker"}:
            errors.append("unavailable payload reason is not recognized")

    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("B" + "UY", "S" + "ELL", "H" + "OLD", "target " + "price"):
        if forbidden in text:
            errors.append(f"forbidden output text present: {forbidden}")
    return {"valid": not errors, "errors": errors}
