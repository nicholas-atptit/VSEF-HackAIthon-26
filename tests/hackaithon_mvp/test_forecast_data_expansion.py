from src.hackaithon_mvp.forecast_data_expansion import (
    inspect_data_expansion_config,
    render_data_expansion_report,
    run_optional_data_expansion,
)


def test_data_expansion_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOW_PROVIDER_DATA_FETCH", raising=False)

    result = run_optional_data_expansion(output_root=str(tmp_path / ".tmp_forecast_edge"))

    assert result["data_expansion_status"] == "disabled_by_default"
    assert result["written_files"] == []


def test_data_expansion_requires_explicit_enabled_config(monkeypatch):
    monkeypatch.setenv("ALLOW_PROVIDER_DATA_FETCH", "1")
    monkeypatch.delenv("DATA_PROVIDER", raising=False)
    monkeypatch.delenv("MAX_TICKERS", raising=False)
    monkeypatch.delenv("START_DATE", raising=False)
    monkeypatch.delenv("END_DATE", raising=False)

    result = inspect_data_expansion_config()

    assert result["data_expansion_status"] == "missing_required_config"
    assert set(result["missing_required_env"]) == {"DATA_PROVIDER", "MAX_TICKERS", "START_DATE", "END_DATE"}


def test_data_expansion_reports_provider_not_configured_without_secret_output(monkeypatch, tmp_path):
    monkeypatch.setenv("ALLOW_PROVIDER_DATA_FETCH", "1")
    monkeypatch.setenv("DATA_PROVIDER", "fixture")
    monkeypatch.setenv("MAX_TICKERS", "3")
    monkeypatch.setenv("START_DATE", "2024-01-01")
    monkeypatch.setenv("END_DATE", "2024-12-31")
    monkeypatch.setenv("DATA_PROVIDER_SECRET", "not-for-output")

    result = run_optional_data_expansion(output_root=str(tmp_path / ".tmp_forecast_edge"))
    report = render_data_expansion_report(result)

    assert result["data_expansion_status"] == "provider_not_configured"
    assert "not-for-output" not in report
