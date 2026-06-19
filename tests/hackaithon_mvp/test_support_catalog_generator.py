from src.hackaithon_mvp.engine_catalog.support_catalog_generator import generate_support_catalog


def test_support_catalog_has_nonzero_generated_engines():
    specs = generate_support_catalog()
    assert specs
    assert all(spec.engine_type == "support" for spec in specs)


def test_support_catalog_has_unique_deterministic_ids_and_no_excluded_scope():
    specs = generate_support_catalog()
    ids = [spec.engine_id for spec in specs]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert not any("qml" in engine_id.lower() or "quantum" in engine_id.lower() for engine_id in ids)
