from src.hackaithon_mvp.engine_catalog.stack_catalog_generator import generate_stack_catalog


def test_stack_catalog_has_nonzero_generated_engines():
    specs = generate_stack_catalog()
    assert specs
    assert all(spec.engine_type == "stack" for spec in specs)


def test_stack_catalog_has_unique_deterministic_ids_and_no_excluded_scope():
    specs = generate_stack_catalog()
    ids = [spec.engine_id for spec in specs]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert not any("qml" in engine_id.lower() or "quantum" in engine_id.lower() for engine_id in ids)
