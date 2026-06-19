import re

from src.hackaithon_mvp.model_diagnostics.registry import list_adapters

FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "trade",
    "allocation",
    "advice",
)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_strings(item)


def test_adapter_metadata_has_no_public_trading_language():
    for adapter in list_adapters():
        metadata_text = " ".join(_walk_strings(adapter.to_metadata())).lower()
        for term in FORBIDDEN_PUBLIC_TERMS:
            assert not re.search(rf"\b{re.escape(term)}\b", metadata_text), (adapter.model_key, term)
