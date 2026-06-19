import pytest

from src.hackaithon_mvp.model_diagnostics.inventory import MODEL_INVENTORY
from src.hackaithon_mvp.model_diagnostics.registry import (
    get_adapter,
    list_adapters,
    list_by_family,
    list_exploratory,
    list_missing_dependency,
)


def test_registry_returns_every_inventory_adapter():
    inventory_keys = {entry["model_key"] for entry in MODEL_INVENTORY}
    registry_keys = {adapter.model_key for adapter in list_adapters()}
    assert registry_keys == inventory_keys


def test_registry_model_keys_are_unique():
    keys = [adapter.model_key for adapter in list_adapters()]
    assert len(keys) == len(set(keys))


def test_get_adapter_returns_metadata_adapter():
    adapter = get_adapter("logistic_l2")
    assert adapter.model_key == "logistic_l2"
    assert adapter.model_family == "classification"


def test_registry_filters_by_family():
    baseline = list_by_family("baseline")
    assert baseline
    assert all(adapter.model_family == "baseline" for adapter in baseline)


def test_registry_exploratory_and_dependency_filters():
    exploratory_keys = {adapter.model_key for adapter in list_exploratory()}
    dependency_keys = {adapter.model_key for adapter in list_missing_dependency()}
    assert "garch_volatility_diagnostic" in exploratory_keys
    assert "bilstm" in exploratory_keys
    assert "catboost" in dependency_keys
    assert "bilstm" in dependency_keys


def test_registry_rejects_excluded_family_filter_and_key():
    with pytest.raises(ValueError):
        list_by_family("qml")
    with pytest.raises(KeyError):
        get_adapter("qml")
