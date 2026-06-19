import re

from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.engine_catalog.stack_catalog_generator import generate_stack_catalog
from src.hackaithon_mvp.engine_catalog.support_catalog_generator import generate_support_catalog
from src.hackaithon_mvp.engine_runtime.engine_runner import run_engine


FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "trade",
    "trading",
    "allocation",
    "advice",
)


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_strings(item)


def _assert_no_forbidden_public_terms(payload):
    text = " ".join(_walk_strings(payload)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert not re.search(rf"\b{re.escape(term)}\b", text), term


def test_generated_engine_metadata_has_no_public_trading_language():
    for specs in (generate_baseline_catalog(), generate_support_catalog(), generate_stack_catalog()):
        for spec in specs:
            _assert_no_forbidden_public_terms(spec.to_dict())


def test_engine_result_has_no_public_trading_language():
    spec = next(
        spec
        for spec in generate_baseline_catalog()
        if spec.engine_id == "classification.logistic_l2.absolute_direction.h40.feature_set_c.threshold_055"
    )
    _assert_no_forbidden_public_terms(run_engine(spec).to_dict())
