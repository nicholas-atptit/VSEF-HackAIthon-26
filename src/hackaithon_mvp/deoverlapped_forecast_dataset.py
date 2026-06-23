"""Build de-overlapped local forecast evaluation rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_require_explicit_output": True,
    "write_root_limited_to_tmp_forecast_repair": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_label_fabrication": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "De-overlapped dataset builder removes duplicate keys and overlapping local rows only."
BINARY_DIRECTIONS = {UP, DOWN}


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _raw(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw")
    return raw if isinstance(raw, dict) else row


def _prediction_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("ticker") or "unspecified"),
        str(row.get("model_id") or "unspecified"),
        str(row.get("horizon") or "unspecified"),
        str(row.get("forecast_timestamp") or "unspecified"),
    )


def _step_position(row: dict[str, Any], fallback: int) -> int:
    raw = _raw(row)
    for key in ("deoverlap_step_index", "_deoverlap_step_index", "source_step_index", "bar_index"):
        value = raw.get(key, row.get(key))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return fallback


def _horizon_steps(value: Any) -> int:
    try:
        steps = int(float(value))
    except (TypeError, ValueError):
        return 1
    return max(1, steps)


def _quality_score(row: dict[str, Any]) -> tuple[int, int, int, int]:
    raw = _raw(row)
    forecast_time = _parse_time(row.get("forecast_timestamp"))
    actual_time = _parse_time(
        raw.get("actual_timestamp")
        or raw.get("future_timestamp")
        or raw.get("target_timestamp")
        or raw.get("label_timestamp")
    )
    valid_binary = int(row.get("predicted_direction") in BINARY_DIRECTIONS and row.get("actual_direction") in BINARY_DIRECTIONS)
    valid_time = int(forecast_time is not None and actual_time is not None and forecast_time < actual_time)
    has_probability = int(isinstance(row.get("predicted_probability"), (int, float)))
    has_actual_return = int(isinstance(row.get("actual_return"), (int, float)))
    return valid_binary, valid_time, has_probability, has_actual_return


def _sort_key(row: dict[str, Any]) -> tuple:
    return (
        _parse_time(row.get("forecast_timestamp")) or datetime.min,
        str(row.get("forecast_timestamp") or ""),
        int(row.get("source_index") or 0),
        str(row.get("ticker") or ""),
        str(row.get("model_id") or ""),
    )


def _to_output_row(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(_raw(row))
    output.setdefault("ticker", row.get("ticker"))
    output.setdefault("model_id", row.get("model_id"))
    output.setdefault("model_family", row.get("model_family"))
    output.setdefault("horizon", row.get("horizon"))
    output.setdefault("forecast_timestamp", row.get("forecast_timestamp"))
    output.setdefault("predicted_direction", row.get("predicted_direction"))
    output.setdefault("actual_direction", row.get("actual_direction"))
    if row.get("predicted_probability") is not None:
        output.setdefault("predicted_probability", row.get("predicted_probability"))
    if row.get("predicted_return") is not None:
        output.setdefault("predicted_return", row.get("predicted_return"))
    if row.get("actual_return") is not None:
        output.setdefault("actual_return", row.get("actual_return"))
    output.setdefault("deoverlap_step_index", row.get("source_index"))
    output["forecast_repair_row_status"] = "clean_deoverlapped"
    return output


def remove_duplicate_prediction_keys(rows: list[dict]) -> dict:
    """Keep one deterministic row per ticker/model/horizon/timestamp key."""

    normalized = normalize_forecast_actual_rows(rows)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[_prediction_key(row)].append(row)

    retained: list[dict[str, Any]] = []
    duplicate_groups: list[dict[str, Any]] = []
    dropped = 0
    for key, group_rows in sorted(grouped.items()):
        ordered = sorted(group_rows, key=_sort_key)
        best_score = max(_quality_score(row) for row in ordered)
        best = next(row for row in ordered if _quality_score(row) == best_score)
        retained.append(best)
        if len(group_rows) > 1:
            dropped += len(group_rows) - 1
            duplicate_groups.append(
                {
                    "ticker": key[0],
                    "model_id": key[1],
                    "horizon": key[2],
                    "forecast_timestamp": key[3],
                    "input_rows": len(group_rows),
                    "dropped_rows": len(group_rows) - 1,
                    "kept_source_index": best.get("source_index"),
                    "selection_rule": "highest_quality_then_earliest_timestamp",
                }
            )
    retained.sort(key=_sort_key)
    return {
        "deduplication_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "retained_rows": len(retained),
        "dropped_duplicate_rows": dropped,
        "duplicate_key_count": len(duplicate_groups),
        "rows": [_to_output_row(row) for row in retained],
        "duplicate_groups": duplicate_groups[:25],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def build_non_overlapping_rows(
    rows: list[dict],
    *,
    horizon_steps: int,
    group_keys: tuple[str, ...] = ("ticker", "horizon"),
) -> dict:
    """Retain rows at least horizon_steps apart within ticker/horizon/model slices."""

    normalized = normalize_forecast_actual_rows(rows)
    effective_keys = tuple(dict.fromkeys((*group_keys, "model_id")))
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[tuple(str(row.get(key) or "unspecified") for key in effective_keys)].append(row)

    retained: list[dict[str, Any]] = []
    dropped_overlap_rows: list[dict[str, Any]] = []
    group_summaries = []
    steps = max(1, int(horizon_steps))
    for key, group_rows in sorted(grouped.items()):
        ordered = sorted(group_rows, key=_sort_key)
        last_kept_position: int | None = None
        last_kept_time: datetime | None = None
        kept = 0
        dropped = 0
        for index, row in enumerate(ordered):
            position = _step_position(row, index)
            current_time = _parse_time(row.get("forecast_timestamp"))
            keep = True
            if last_kept_position is not None:
                keep = position - last_kept_position >= steps
            elif last_kept_time is not None and current_time is not None:
                keep = (current_time - last_kept_time).days >= steps
            if keep:
                retained.append(row)
                kept += 1
                last_kept_position = position
                last_kept_time = current_time
            else:
                dropped += 1
                dropped_overlap_rows.append(row)
        group_summaries.append(
            {
                "group": "|".join(f"{field}={value}" for field, value in zip(effective_keys, key)),
                "input_rows": len(ordered),
                "retained_rows": kept,
                "dropped_overlap_rows": dropped,
                "horizon_steps": steps,
            }
        )
    retained.sort(key=_sort_key)
    return {
        "deoverlap_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "horizon_steps": steps,
        "group_keys": list(effective_keys),
        "retained_rows": len(retained),
        "dropped_overlap_rows": len(dropped_overlap_rows),
        "rows": [_to_output_row(row) for row in retained],
        "group_summaries": group_summaries,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def build_deoverlapped_forecast_dataset(rows: list[dict]) -> dict:
    """Remove duplicate prediction keys and overlapping target windows."""

    dedup = remove_duplicate_prediction_keys(rows)
    dedup_rows = list(dedup.get("rows") or [])
    grouped_by_horizon: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dedup_rows:
        grouped_by_horizon[str(row.get("horizon") or "unspecified")].append(row)

    retained: list[dict[str, Any]] = []
    dropped_overlap = 0
    horizon_summaries = []
    for horizon, horizon_rows in sorted(grouped_by_horizon.items(), key=lambda item: (_horizon_steps(item[0]), item[0])):
        horizon_steps = _horizon_steps(horizon)
        result = build_non_overlapping_rows(horizon_rows, horizon_steps=horizon_steps)
        retained.extend(result.get("rows") or [])
        dropped_overlap += int(result.get("dropped_overlap_rows") or 0)
        horizon_summaries.append(
            {
                "horizon": horizon,
                "horizon_steps": horizon_steps,
                "input_rows": len(horizon_rows),
                "retained_rows": result.get("retained_rows"),
                "dropped_overlap_rows": result.get("dropped_overlap_rows"),
            }
        )
    retained.sort(
        key=lambda row: (
            str(row.get("ticker") or ""),
            _horizon_steps(row.get("horizon")),
            str(row.get("model_id") or ""),
            str(row.get("forecast_timestamp") or ""),
        )
    )
    by_horizon = Counter(str(row.get("horizon") or "unspecified") for row in retained)
    by_model = Counter(str(row.get("model_id") or "unspecified") for row in retained)
    return {
        "dataset_status": "completed" if rows else "not_ready_no_rows",
        "input_rows": len(rows),
        "deduplicated_rows": dedup.get("retained_rows"),
        "retained_rows": len(retained),
        "dropped_duplicate_rows": dedup.get("dropped_duplicate_rows"),
        "dropped_overlap_rows": dropped_overlap,
        "rows_by_horizon": dict(sorted(by_horizon.items())),
        "rows_by_model": dict(sorted(by_model.items())),
        "horizon_summaries": horizon_summaries,
        "deduplication": {key: value for key, value in dedup.items() if key != "rows"},
        "rows": retained,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_deoverlapped_dataset_report(result: dict) -> str:
    """Render a compact de-overlapped dataset report."""

    lines = [
        "# De-overlapped Forecast Dataset",
        "",
        f"Dataset status: {result.get('dataset_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Rows after duplicate-key repair: {result.get('deduplicated_rows')}",
        f"Retained rows: {result.get('retained_rows')}",
        f"Dropped duplicate rows: {result.get('dropped_duplicate_rows')}",
        f"Dropped overlap rows: {result.get('dropped_overlap_rows')}",
        f"Rows by horizon: {result.get('rows_by_horizon')}",
        "",
        "Horizon summaries:",
    ]
    for item in result.get("horizon_summaries", []):
        lines.append(
            "- h{horizon}: input={input_rows}, retained={retained_rows}, dropped_overlap={dropped_overlap_rows}".format(
                **item
            )
        )
    if not result.get("horizon_summaries"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "Rows are removed only for duplicate keys or overlapping target windows; labels are not fabricated.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    if not any(part.lower().startswith(".tmp_forecast_repair") for part in path.parts):
        raise ValueError("write-output must be under .tmp_forecast_repair")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a de-overlapped local forecast dataset.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--write-output", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_forecast_accuracy_rows(args.input)
        result = build_deoverlapped_forecast_dataset(rows)
        if args.write_output:
            _write_jsonl(Path(args.write_output), result.get("rows") or [])
            result["written_output"] = args.write_output
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    public_result = {key: value for key, value in result.items() if key != "rows"}
    if args.format == "report":
        print(render_deoverlapped_dataset_report(public_result), end="")
    else:
        print(json.dumps(public_result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
