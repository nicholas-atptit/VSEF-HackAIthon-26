from pathlib import Path

from src.hackaithon_mvp.model_diagnostics.inventory import (
    ALLOWED_MODEL_FAMILIES,
    EXCLUDED_FROM_MVP,
    MODEL_INVENTORY,
)


def test_inventory_has_expected_non_qml_families():
    families = {entry["model_family"] for entry in MODEL_INVENTORY}
    assert families == set(ALLOWED_MODEL_FAMILIES)
    assert "qml" not in families
    assert "quantum" not in families


def test_inventory_contains_created_adapter_files():
    for entry in MODEL_INVENTORY:
        path = Path(entry["adapter_file"])
        assert path.exists(), entry["model_key"]
        assert entry["adapter_status"] == "created"


def test_inventory_preserves_dependency_gated_non_qml_models():
    statuses = {entry["model_key"]: entry["dependency_status"] for entry in MODEL_INVENTORY}
    assert statuses["catboost"] == "missing_dependency"
    assert statuses["garch_volatility_diagnostic"] == "optional_dependency"
    assert statuses["bilstm"] == "optional_dependency"


def test_excluded_scope_constants_present_without_allowed_family_leak():
    assert EXCLUDED_FROM_MVP == {"qml", "quantum", "quantum_machine_learning"}
    for entry in MODEL_INVENTORY:
        lowered = f"{entry['model_key']} {entry['model_family']}".lower()
        assert "qml" not in lowered
        assert "quantum" not in lowered
