import ast
import re
from pathlib import Path

from src.hackaithon_mvp.model_diagnostics.base import BaseDiagnosticAdapter
from src.hackaithon_mvp.model_diagnostics.inventory import MODEL_INVENTORY
from src.hackaithon_mvp.model_diagnostics.registry import get_adapter

ADAPTER_ROOT = Path("src/hackaithon_mvp/model_diagnostics")
SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*_diagnostic\.py$")
HEAVY_IMPORTS = (
    "sklearn",
    "xgboost",
    "lightgbm",
    "catboost",
    "torch",
    "tensorflow",
    "qiskit",
    "pennylane",
)


def test_adapter_files_use_snake_case_naming():
    files = sorted(ADAPTER_ROOT.glob("*/*_diagnostic.py"))
    assert files
    for path in files:
        assert SNAKE_RE.match(path.name), path
        assert "qml" not in path.parts
        assert "quantum" not in path.parts


def test_adapter_classes_end_with_diagnostic_adapter_and_inherit_base():
    for entry in MODEL_INVENTORY:
        adapter = get_adapter(entry["model_key"])
        assert adapter.__class__.__name__.endswith("DiagnosticAdapter")
        assert isinstance(adapter, BaseDiagnosticAdapter)


def test_no_adapter_has_model_execution_methods():
    forbidden_methods = {"fit", "predict", "train", "infer"}
    for entry in MODEL_INVENTORY:
        adapter = get_adapter(entry["model_key"])
        assert forbidden_methods.isdisjoint(adapter.__class__.__dict__)


def test_adapters_do_not_import_heavy_frameworks():
    for path in ADAPTER_ROOT.glob("*/*_diagnostic.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        assert not set(imports).intersection(HEAVY_IMPORTS), path
