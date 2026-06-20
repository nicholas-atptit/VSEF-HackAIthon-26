"""Storage interface contracts for future market data readiness checks."""

from __future__ import annotations

from typing import Protocol

from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


class MarketDataStore(Protocol):
    def get_available_bars(self, ticker: str, timeframe: str) -> int:
        ...

    def has_timeframe(self, ticker: str, timeframe: str) -> bool:
        ...

    def describe(self) -> dict:
        ...


class InMemoryMarketDataStore:
    """Small test/demo store. It is not a database implementation."""

    def __init__(self, availability: dict[tuple[str, str], int] | None = None) -> None:
        self._availability: dict[tuple[str, str], int] = {}
        for key, value in (availability or {}).items():
            ticker, timeframe = key
            self.set_available_bars(ticker, timeframe, value)

    @staticmethod
    def _key(ticker: str, timeframe: str) -> tuple[str, str]:
        normalized_ticker = str(ticker).strip().upper()
        if not normalized_ticker:
            raise ValueError("ticker must be non-empty")
        return normalized_ticker, normalize_timeframe(timeframe)

    def set_available_bars(self, ticker: str, timeframe: str, bars: int) -> None:
        bar_count = int(bars)
        if bar_count < 0:
            raise ValueError("available bars must be non-negative")
        self._availability[self._key(ticker, timeframe)] = bar_count

    def get_available_bars(self, ticker: str, timeframe: str) -> int:
        return self._availability.get(self._key(ticker, timeframe), 0)

    def has_timeframe(self, ticker: str, timeframe: str) -> bool:
        return self._key(ticker, timeframe) in self._availability

    def describe(self) -> dict:
        return {
            "store_type": "in_memory_test_stub",
            "database_created": False,
            "provider_access_enabled": False,
            "records_count": len(self._availability),
        }
