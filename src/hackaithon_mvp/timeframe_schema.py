"""Supported static timeframe schema for the HackAIthon MVP."""

from __future__ import annotations

import re


REQUIRED_TIMEFRAME_INPUTS = (
    "1p",
    "2p",
    "5p",
    "10p",
    "1h",
    "2h",
    "5h",
    "10h",
    "1 ngày",
    "2 ngày",
    "3 ngày",
    "4 ngày",
    "5 ngày",
    "10 ngày",
    "15 ngày",
    "20 ngày",
    "30 ngày",
    "40 ngày",
)

CANONICAL_TIMEFRAMES = (
    "1m",
    "2m",
    "5m",
    "10m",
    "1h",
    "2h",
    "5h",
    "10h",
    "1d",
    "2d",
    "3d",
    "4d",
    "5d",
    "10d",
    "15d",
    "20d",
    "30d",
    "40d",
)

_MINUTE_STEPS = (1, 2, 5, 10)
_HOUR_STEPS = (1, 2, 5, 10)
_DAY_STEPS = (1, 2, 3, 4, 5, 10, 15, 20, 30, 40)
_UNIT_LABELS = {"m": "minute", "h": "hour", "d": "day"}


def _build_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for step in _MINUTE_STEPS:
        canonical = f"{step}m"
        aliases.update(
            {
                f"{step}p": canonical,
                f"{step} phút": canonical,
                f"{step}m": canonical,
                f"{step}min": canonical,
                f"{step}minute": canonical,
            }
        )
    for step in _HOUR_STEPS:
        canonical = f"{step}h"
        aliases[canonical] = canonical
    for step in _DAY_STEPS:
        canonical = f"{step}d"
        aliases.update(
            {
                f"{step} ngày": canonical,
                f"{step}d": canonical,
                f"{step}day": canonical,
                f"{step} day": canonical,
            }
        )
    return aliases


TIMEFRAME_ALIASES = _build_aliases()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_timeframe(value: str) -> str:
    """Return the canonical timeframe value, or raise for unsupported input."""

    if not isinstance(value, str):
        raise ValueError(f"unsupported timeframe: {value!r}")
    cleaned = _clean(value)
    if not cleaned:
        raise ValueError("unsupported timeframe: empty value")
    try:
        return TIMEFRAME_ALIASES[cleaned]
    except KeyError as exc:
        supported = ", ".join(REQUIRED_TIMEFRAME_INPUTS)
        raise ValueError(f"unsupported timeframe: {value!r}. Supported inputs: {supported}") from exc


def assert_supported_timeframe(value: str) -> None:
    normalize_timeframe(value)


def timeframe_to_horizon_steps(value: str) -> int:
    canonical = normalize_timeframe(value)
    return int(canonical[:-1])


def timeframe_unit(value: str) -> str:
    canonical = normalize_timeframe(value)
    return _UNIT_LABELS[canonical[-1]]


def is_intraday_timeframe(value: str) -> bool:
    return timeframe_unit(value) in {"minute", "hour"}


def is_daily_timeframe(value: str) -> bool:
    return timeframe_unit(value) == "day"
