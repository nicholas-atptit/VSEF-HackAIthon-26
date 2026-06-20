"""Future data contract definitions for HackAIthon MVP readiness checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict

from src.hackaithon_mvp.timeframe_schema import (
    REQUIRED_TIMEFRAME_INPUTS,
    normalize_timeframe,
    timeframe_to_horizon_steps,
    timeframe_unit,
)


DEFAULT_TICKERS = (
    "VCB",
    "BID",
    "CTG",
    "TCB",
    "VPB",
    "MBB",
    "ACB",
    "HDB",
    "STB",
    "VIB",
    "TPB",
    "SHB",
    "EIB",
    "MSB",
    "OCB",
    "LPB",
    "SSB",
    "ABB",
    "BAB",
    "BVB",
    "KLB",
    "NAB",
    "PGB",
    "SGB",
    "VAB",
    "VBB",
    "VCC",
    "VDD",
    "VEE",
    "VFF",
)


class DataAvailabilityRequest(TypedDict):
    ticker: str
    timeframe: str
    required_bars: int


class DataAvailabilityResult(TypedDict):
    ticker: str
    timeframe: str
    required_bars: int
    available_bars: int
    ready: bool


class DatasetManifest(TypedDict, total=False):
    dataset_id: str
    created_at: str
    tickers: list[str]
    timeframes: list[str]
    rows_count: int
    source_description: str
    metadata: dict[str, Any]


def _normalize_ticker(value: str) -> str:
    ticker = str(value).strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty uppercase string")
    if ticker != str(value).strip():
        raise ValueError("ticker must be uppercase")
    return ticker


def _timestamp_to_string(value: str | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        timestamp = value.strip()
        if not timestamp:
            raise ValueError("timestamp must be non-empty")
        if "T" not in timestamp and " " not in timestamp and len(timestamp) < 10:
            raise ValueError("timestamp must be ISO-like")
        return timestamp
    raise ValueError("timestamp must be an ISO-like string or datetime")


def _numeric(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number:
        raise ValueError(f"{field_name} must be numeric")
    return number


def _positive_price(value: Any, field_name: str) -> float:
    number = _numeric(value, field_name)
    if number <= 0 or number > 1_000_000_000:
        raise ValueError(f"{field_name} must be within a broadly valid numeric range")
    return number


@dataclass(frozen=True)
class BarRecord:
    ticker: str
    timeframe: str
    timestamp: str | datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str | None = None
    adjusted_close: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ticker = _normalize_ticker(self.ticker)
        timeframe = normalize_timeframe(self.timeframe)
        timestamp = _timestamp_to_string(self.timestamp)
        open_value = _positive_price(self.open, "open")
        high_value = _positive_price(self.high, "high")
        low_value = _positive_price(self.low, "low")
        close_value = _positive_price(self.close, "close")
        volume_value = _numeric(self.volume, "volume")
        if volume_value < 0:
            raise ValueError("volume must be non-negative")
        if high_value < low_value:
            raise ValueError("high must be greater than or equal to low")
        if not low_value <= open_value <= high_value:
            raise ValueError("open must be within the high/low range")
        if not low_value <= close_value <= high_value:
            raise ValueError("close must be within the high/low range")
        adjusted_close = None if self.adjusted_close is None else _positive_price(self.adjusted_close, "adjusted_close")

        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "open", open_value)
        object.__setattr__(self, "high", high_value)
        object.__setattr__(self, "low", low_value)
        object.__setattr__(self, "close", close_value)
        object.__setattr__(self, "volume", volume_value)
        object.__setattr__(self, "adjusted_close", adjusted_close)
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class TimeframeDataRequirement:
    ticker: str
    input_timeframe: str
    canonical_timeframe: str
    timeframe_unit: str
    horizon_steps: int
    cases_required: int
    lookback_bars: int
    safety_margin_bars: int
    required_bars: int


def estimate_required_bars(
    cases_required: int,
    lookback_bars: int,
    horizon_steps: int,
    safety_margin_bars: int = 100,
) -> int:
    values = {
        "cases_required": cases_required,
        "lookback_bars": lookback_bars,
        "horizon_steps": horizon_steps,
        "safety_margin_bars": safety_margin_bars,
    }
    for field_name, value in values.items():
        if int(value) < 0:
            raise ValueError(f"{field_name} must be non-negative")
    return int(cases_required) + int(lookback_bars) + int(horizon_steps) + int(safety_margin_bars)


def build_timeframe_requirements(
    tickers: tuple[str, ...],
    timeframe_inputs: tuple[str, ...],
    cases_per_pair: int = 10_000,
    lookback_bars: int = 120,
    safety_margin_bars: int = 100,
) -> tuple[TimeframeDataRequirement, ...]:
    requirements: list[TimeframeDataRequirement] = []
    for ticker_value in tickers:
        ticker = _normalize_ticker(ticker_value)
        for input_timeframe in timeframe_inputs:
            canonical = normalize_timeframe(input_timeframe)
            horizon_steps = timeframe_to_horizon_steps(canonical)
            requirements.append(
                TimeframeDataRequirement(
                    ticker=ticker,
                    input_timeframe=input_timeframe,
                    canonical_timeframe=canonical,
                    timeframe_unit=timeframe_unit(canonical),
                    horizon_steps=horizon_steps,
                    cases_required=int(cases_per_pair),
                    lookback_bars=int(lookback_bars),
                    safety_margin_bars=int(safety_margin_bars),
                    required_bars=estimate_required_bars(
                        int(cases_per_pair),
                        int(lookback_bars),
                        horizon_steps,
                        int(safety_margin_bars),
                    ),
                )
            )
    return tuple(requirements)


def build_default_timeframe_requirements(
    cases_per_pair: int = 10_000,
    lookback_bars: int = 120,
    safety_margin_bars: int = 100,
) -> tuple[TimeframeDataRequirement, ...]:
    return build_timeframe_requirements(
        DEFAULT_TICKERS,
        REQUIRED_TIMEFRAME_INPUTS,
        cases_per_pair=cases_per_pair,
        lookback_bars=lookback_bars,
        safety_margin_bars=safety_margin_bars,
    )
