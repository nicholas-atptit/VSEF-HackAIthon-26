"""Local forecast-vs-actual evaluation presentation for HackAIthon MVP outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


ALLOWED_FORECAST_DIAGNOSTICS = frozenset(
    {
        "positive_bias",
        "negative_bias",
        "neutral_or_uncertain",
        "insufficient_evidence",
        "exploratory_only",
    }
)
ALLOWED_ACTUAL_DIRECTION_LABELS = frozenset({"positive", "negative", "flat"})
DIRECTIONAL_DIAGNOSTICS = frozenset({"positive_bias", "negative_bias"})
ABSTENTION_DIAGNOSTICS = frozenset({"neutral_or_uncertain", "insufficient_evidence", "exploratory_only"})
REQUIRED_FIELDS = (
    "ticker",
    "timeframe",
    "prediction_timestamp",
    "horizon_steps",
    "forecast_diagnostic",
    "actual_future_return",
    "actual_direction_label",
)
OPTIONAL_FIELDS = (
    "engine_id",
    "model_key",
    "model_family",
    "diagnostic_score",
    "confidence",
    "route",
    "risk_level",
    "split_id",
    "actual_timestamp",
    "source",
)
CLAIM_BOUNDARY = {
    "actual_data_required": True,
    "no_live_data": True,
    "no_provider_api_calls": True,
    "no_training": True,
    "no_inference": True,
    "not_financial_advice": True,
    "not_performance_guarantee": True,
}
NON_CLAIM_TEXT = "Local actual data is required for accuracy; no live data or model execution is performed."


def _safe_float(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number:
        raise ValueError(f"{field_name} must be numeric")
    return number


def _optional_float(value: Any, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    return _safe_float(value, field_name)


def derive_actual_direction_label(actual_future_return: float) -> str:
    if actual_future_return > 0:
        return "positive"
    if actual_future_return < 0:
        return "negative"
    return "flat"


def validate_forecast_actual_row(row: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing required forecast-actual fields: {missing}")

    ticker = str(row["ticker"]).strip().upper()
    if not ticker:
        raise ValueError("ticker must be non-empty")
    timeframe = normalize_timeframe(str(row["timeframe"]))
    prediction_timestamp = str(row["prediction_timestamp"]).strip()
    if not prediction_timestamp:
        raise ValueError("prediction_timestamp must be non-empty")
    horizon_steps = int(row["horizon_steps"])
    if horizon_steps <= 0:
        raise ValueError("horizon_steps must be positive")
    forecast_diagnostic = str(row["forecast_diagnostic"]).strip()
    if forecast_diagnostic not in ALLOWED_FORECAST_DIAGNOSTICS:
        raise ValueError(f"unsupported forecast_diagnostic: {forecast_diagnostic}")
    actual_future_return = _safe_float(row["actual_future_return"], "actual_future_return")
    actual_direction_label = str(row.get("actual_direction_label") or "").strip().lower()
    if not actual_direction_label:
        actual_direction_label = derive_actual_direction_label(actual_future_return)
    if actual_direction_label not in ALLOWED_ACTUAL_DIRECTION_LABELS:
        raise ValueError(f"unsupported actual_direction_label: {actual_direction_label}")

    normalized = {
        "ticker": ticker,
        "timeframe": timeframe,
        "prediction_timestamp": prediction_timestamp,
        "horizon_steps": horizon_steps,
        "forecast_diagnostic": forecast_diagnostic,
        "actual_future_return": actual_future_return,
        "actual_direction_label": actual_direction_label,
    }
    for field in OPTIONAL_FIELDS:
        value = row.get(field)
        if value in (None, ""):
            continue
        if field in {"diagnostic_score", "confidence"}:
            normalized[field] = _optional_float(value, field)
        else:
            normalized[field] = str(value).strip()
    return normalized


def _load_json_payload(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        rows = payload.get("rows")
    else:
        rows = payload
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON forecast-actual payload must be a list of objects or an object with rows")
    return rows


def load_forecast_actual_rows(path: str) -> tuple[dict, ...]:
    local_path = Path(path)
    if not local_path.exists() or not local_path.is_file():
        raise FileNotFoundError(f"forecast-actual input file not found: {path}")
    suffix = local_path.suffix.lower()
    if suffix == ".csv":
        with local_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    elif suffix == ".json":
        rows = _load_json_payload(local_path)
    elif suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in local_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("JSONL forecast-actual payload must contain objects")
    else:
        raise ValueError("forecast-actual input must be .csv, .json, or .jsonl")
    return tuple(validate_forecast_actual_row(row) for row in rows)


def _is_correct(row: dict[str, Any]) -> bool | None:
    diagnostic = row["forecast_diagnostic"]
    actual = row["actual_direction_label"]
    if diagnostic == "positive_bias":
        return actual == "positive"
    if diagnostic == "negative_bias":
        return actual == "negative"
    return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _sort_key(row: dict[str, Any]) -> tuple:
    diagnostic_score = row.get("diagnostic_score")
    confidence = row.get("confidence")
    return (
        -(float(diagnostic_score) if diagnostic_score is not None else -1.0),
        -(float(confidence) if confidence is not None else -1.0),
        row.get("ticker", ""),
        row.get("timeframe", ""),
        row.get("prediction_timestamp", ""),
        row.get("engine_id", ""),
    )


def _directional_metrics(rows: tuple[dict, ...]) -> dict[str, Any]:
    rows_total = len(rows)
    eligible = [row for row in rows if row["forecast_diagnostic"] in DIRECTIONAL_DIAGNOSTICS]
    abstained_rows = rows_total - len(eligible)
    correct_rows = [row for row in eligible if _is_correct(row) is True]
    incorrect_rows = [row for row in eligible if _is_correct(row) is False]
    positive_predictions = [row for row in eligible if row["forecast_diagnostic"] == "positive_bias"]
    negative_predictions = [row for row in eligible if row["forecast_diagnostic"] == "negative_bias"]
    actual_positive = [row for row in eligible if row["actual_direction_label"] == "positive"]
    actual_negative = [row for row in eligible if row["actual_direction_label"] == "negative"]
    positive_correct = [row for row in positive_predictions if row["actual_direction_label"] == "positive"]
    negative_correct = [row for row in negative_predictions if row["actual_direction_label"] == "negative"]
    positive_recall = _ratio(len([row for row in actual_positive if row["forecast_diagnostic"] == "positive_bias"]), len(actual_positive))
    negative_recall = _ratio(len([row for row in actual_negative if row["forecast_diagnostic"] == "negative_bias"]), len(actual_negative))
    warnings: list[str] = []
    if positive_recall is None or negative_recall is None:
        balanced_accuracy = None
        warnings.append("balanced directional accuracy unavailable because a realized direction class is missing")
    else:
        balanced_accuracy = round((positive_recall + negative_recall) / 2, 6)

    return {
        "rows_total": rows_total,
        "eligible_directional_rows": len(eligible),
        "abstained_rows": abstained_rows,
        "correct_directional_rows": len(correct_rows),
        "incorrect_directional_rows": len(incorrect_rows),
        "directional_accuracy": _ratio(len(correct_rows), len(eligible)),
        "coverage_ratio": _ratio(len(eligible), rows_total),
        "abstention_ratio": _ratio(abstained_rows, rows_total),
        "positive_precision": _ratio(len(positive_correct), len(positive_predictions)),
        "negative_precision": _ratio(len(negative_correct), len(negative_predictions)),
        "balanced_directional_accuracy": balanced_accuracy,
        "mean_actual_return_when_positive_bias": _mean([row["actual_future_return"] for row in positive_predictions]),
        "mean_actual_return_when_negative_bias": _mean([row["actual_future_return"] for row in negative_predictions]),
        "warnings": warnings,
    }


def _group_metrics(rows: tuple[dict, ...], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        group_key = str(row.get(key) or "unspecified")
        groups.setdefault(group_key, []).append(row)
    return {group_key: _directional_metrics(tuple(group_rows)) for group_key, group_rows in sorted(groups.items())}


def _missing_result() -> dict[str, Any]:
    return {
        "actual_data_status": "missing",
        "rows_total": 0,
        "eligible_directional_rows": 0,
        "abstained_rows": 0,
        "correct_directional_rows": 0,
        "incorrect_directional_rows": 0,
        "directional_accuracy": None,
        "coverage_ratio": None,
        "abstention_ratio": None,
        "positive_precision": None,
        "negative_precision": None,
        "balanced_directional_accuracy": None,
        "mean_actual_return_when_positive_bias": None,
        "mean_actual_return_when_negative_bias": None,
        "by_timeframe": {},
        "by_ticker": {},
        "by_model_family": {},
        "top_k_summary": None,
        "warnings": ["actual realized data was not provided"],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def evaluate_forecast_vs_actual(rows: tuple[dict, ...], top_k: int | None = None) -> dict:
    normalized_rows = tuple(validate_forecast_actual_row(row) for row in rows)
    if not normalized_rows:
        return _missing_result()
    metrics = _directional_metrics(normalized_rows)
    top_k_summary = None
    if top_k is not None:
        selected = tuple(sorted((row for row in normalized_rows if row["forecast_diagnostic"] in DIRECTIONAL_DIAGNOSTICS), key=_sort_key)[: int(top_k)])
        top_k_summary = {
            "top_k": int(top_k),
            "selected_rows": len(selected),
            **_directional_metrics(selected),
        }
    return {
        "actual_data_status": "provided",
        **metrics,
        "by_timeframe": _group_metrics(normalized_rows, "timeframe"),
        "by_ticker": _group_metrics(normalized_rows, "ticker"),
        "by_model_family": _group_metrics(normalized_rows, "model_family"),
        "top_k_summary": top_k_summary,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _format_metric(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def _compact_group_lines(groups: dict[str, dict[str, Any]]) -> list[str]:
    if not groups:
        return ["No grouped rows available."]
    return [
        f"- {name}: rows={summary['rows_total']}, coverage={_format_metric(summary['coverage_ratio'])}, "
        f"directional_accuracy={_format_metric(summary['directional_accuracy'])}"
        for name, summary in groups.items()
    ]


def render_forecast_actual_report(evaluation: dict) -> str:
    lines = [
        "# HackAIthon MVP Forecast Actual Evaluation",
        "",
        "## Data Status",
        f"Actual data status: {evaluation.get('actual_data_status', 'missing')}",
        "",
        "## Scope",
        "Baseline ML-only diagnostic evaluation using local realized rows when provided.",
        "",
        "## Overall Accuracy",
    ]
    if evaluation.get("actual_data_status") == "missing":
        lines.append("Accuracy is unavailable because local realized rows were not provided.")
    else:
        lines.extend(
            [
                f"Rows total: {evaluation.get('rows_total', 0)}",
                f"Directional accuracy: {_format_metric(evaluation.get('directional_accuracy'))}",
                f"Balanced directional accuracy: {_format_metric(evaluation.get('balanced_directional_accuracy'))}",
            ]
        )
    lines.extend(
        [
            "",
            "## Coverage and Abstention",
            f"Coverage ratio: {_format_metric(evaluation.get('coverage_ratio'))}",
            f"Abstention ratio: {_format_metric(evaluation.get('abstention_ratio'))}",
            "",
            "## By Timeframe",
            *_compact_group_lines(evaluation.get("by_timeframe", {})),
            "",
            "## By Ticker",
            *_compact_group_lines(evaluation.get("by_ticker", {})),
            "",
            "## By Model Family",
            *_compact_group_lines(evaluation.get("by_model_family", {})),
        ]
    )
    if evaluation.get("top_k_summary") is not None:
        top_k = evaluation["top_k_summary"]
        lines.extend(
            [
                "",
                "## Top-K Summary",
                f"Top-K: {top_k.get('top_k')}",
                f"Selected rows: {top_k.get('selected_rows')}",
                f"Directional accuracy: {_format_metric(top_k.get('directional_accuracy'))}",
            ]
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "Actual local rows are required for accuracy.",
            "No live data, provider API calls, model training, model inference, or benchmark rerun is performed.",
            "This report is diagnostic only.",
            str(evaluation.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_output(path: str, content: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate forecast diagnostics against local realized rows.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--write", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_forecast_actual_rows(args.input) if args.input else tuple()
        evaluation = evaluate_forecast_vs_actual(rows, top_k=args.top_k)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    if args.format == "report":
        output = render_forecast_actual_report(evaluation)
    else:
        output = json.dumps(evaluation, indent=2, sort_keys=True) + "\n"
    if args.write:
        _write_output(args.write, output)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
