import json
import re
from pathlib import Path

from src.hackaithon_mvp.local_storage.availability_index import build_availability_index
from src.hackaithon_mvp.local_storage.parquet_adapter import detect_parquet_capability, write_dataset_records
from src.hackaithon_mvp.local_storage.storage_paths import build_partition_path


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\bfinancial advice\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bdeployment\b",
    r"\bapproval\b",
    r"\bclient relationship\b",
)
FORBIDDEN_RUNTIME_TERMS = ("provider.get", "requests.get", "fit(", "predict(", "train(", "infer(")


def _assert_no_forbidden_terms(payload) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, text) is None, pattern


def test_local_storage_outputs_have_no_forbidden_public_terms(tmp_path):
    records = (
        {"ticker": "VCB", "timeframe": "1d", "timestamp": "2026-06-20T00:00:00+07:00", "value": 1},
    )
    output = {
        "capability": detect_parquet_capability(),
        "path": build_partition_path(str(tmp_path), "market_bars", ticker="vcb", timeframe="1 ngày", date="2026-06-20"),
        "write": write_dataset_records(
            str(tmp_path), "market_bars", records, ticker="VCB", timeframe="1d", date="2026-06-20"
        ),
        "availability": build_availability_index(records),
    }

    _assert_no_forbidden_terms(output)


def test_local_storage_package_has_no_provider_or_model_runtime_calls():
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in Path("src/hackaithon_mvp/local_storage").glob("*.py"))

    for term in FORBIDDEN_RUNTIME_TERMS:
        assert term not in source
