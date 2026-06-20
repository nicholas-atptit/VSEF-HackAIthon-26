import pytest

from src.hackaithon_mvp.storage_contract import InMemoryMarketDataStore, MarketDataStore


def test_in_memory_store_satisfies_market_data_store_protocol():
    store: MarketDataStore = InMemoryMarketDataStore()
    store.set_available_bars("VCB", "1 ngày", 123)

    assert store.get_available_bars("VCB", "1d") == 123
    assert store.has_timeframe("VCB", "1d") is True
    assert store.has_timeframe("VCB", "2d") is False
    assert store.describe()["database_created"] is False
    assert store.describe()["provider_access_enabled"] is False


def test_in_memory_store_rejects_negative_bar_counts():
    store = InMemoryMarketDataStore()

    with pytest.raises(ValueError, match="non-negative"):
        store.set_available_bars("VCB", "1d", -1)
