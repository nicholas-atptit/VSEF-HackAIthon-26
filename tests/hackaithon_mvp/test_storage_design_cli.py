import json
import re
import subprocess
import sys


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bclient relationship\b",
)


def test_storage_design_cli_outputs_neutral_json():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.storage_design"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)

    assert output["canonical_data_format"] == "parquet"
    assert output["planned_query_adapter"] == "duckdb_compatible"
    assert output["database_created"] is False
    assert output["data_gateway_created"] is False
    assert output["live_data_enabled"] is False
    assert output["provider_calls_enabled"] is False
    lowered = completed.stdout.lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern
