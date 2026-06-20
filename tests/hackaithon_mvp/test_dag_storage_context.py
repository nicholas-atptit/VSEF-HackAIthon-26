from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_storage_bridge import load_static_context_from_storage
from src.hackaithon_mvp.local_storage.parquet_adapter import write_dataset_records


MARKET_BARS = (
    {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": "2026-01-01T00:00:00+07:00",
        "open": 1,
        "high": 2,
        "low": 1,
        "close": 2,
        "volume": 100,
    },
    {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": "2026-01-02T00:00:00+07:00",
        "open": 2,
        "high": 3,
        "low": 2,
        "close": 3,
        "volume": 120,
    },
)


def test_storage_context_missing_returns_safe_empty_context(tmp_path):
    context = load_static_context_from_storage(
        storage_root=str(tmp_path),
        ticker="VCB",
        timeframe="1 ngày",
        date="2026-01-01",
    )

    assert context["storage_context_status"] == "missing"
    assert context["market_bar_count"] == 0
    assert context["availability_index"]["total_records"] == 0


def test_storage_context_provided_returns_count_and_availability_index(tmp_path):
    write_dataset_records(
        str(tmp_path),
        "market_bars",
        MARKET_BARS,
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
    )

    context = load_static_context_from_storage(
        storage_root=str(tmp_path),
        ticker="vcb",
        timeframe="1 ngày",
        date="2026-01-01",
    )

    assert context["storage_context_status"] == "provided"
    assert context["market_bar_count"] == 2
    assert context["availability_index"]["group_count"] == 1
    assert context["availability_index"]["groups"][0]["ticker"] == "VCB"


def test_dag_execution_works_with_and_without_storage_context(tmp_path):
    no_storage = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
    )
    assert "storage_context_status" not in no_storage["final_state"]

    context = load_static_context_from_storage(
        storage_root=str(tmp_path),
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
    )
    with_storage = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": "1 ngày", "horizon_steps": 1},
        storage_context=context,
    )

    assert with_storage["execution_status"] == "completed_with_warnings"
    assert with_storage["final_state"]["storage_context_status"] == "missing"
    assert with_storage["final_state"]["market_bar_count"] == 0
    assert with_storage["final_state"]["local_storage_available"] is False
