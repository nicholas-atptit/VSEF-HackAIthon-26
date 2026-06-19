from src.hackaithon_mvp.engine_catalog.baseline_catalog_generator import generate_baseline_catalog
from src.hackaithon_mvp.model_diagnostics.registry import list_adapters


def test_baseline_catalog_has_more_engines_than_adapters():
    specs = generate_baseline_catalog()
    assert specs
    assert len(specs) > len(list_adapters())


def test_baseline_catalog_has_unique_deterministic_ids():
    specs = generate_baseline_catalog()
    ids = [spec.engine_id for spec in specs]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_baseline_catalog_has_no_excluded_engine_ids():
    for spec in generate_baseline_catalog():
        lowered = spec.engine_id.lower()
        assert "qml" not in lowered
        assert "quantum" not in lowered
