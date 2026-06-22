from src.hackaithon_mvp.optional_provider_data_fetch import (
    render_optional_provider_data_fetch_report,
    run_optional_provider_data_fetch,
)


def test_provider_fetch_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_PROVIDER_DATA_FETCH", raising=False)

    result = run_optional_provider_data_fetch()

    assert result["provider_fetch_status"] == "disabled_by_default"
    assert result["row_count"] == 0


def test_provider_fetch_requires_provider_when_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_PROVIDER_DATA_FETCH", "1")
    monkeypatch.delenv("DATA_PROVIDER", raising=False)

    result = run_optional_provider_data_fetch()

    assert result["provider_fetch_status"] == "provider_not_configured"


def test_provider_fetch_contract_report_hides_secrets(monkeypatch):
    monkeypatch.setenv("ALLOW_PROVIDER_DATA_FETCH", "1")
    monkeypatch.setenv("DATA_PROVIDER", "local_contract")
    monkeypatch.setenv("MAX_TICKERS", "3")

    report = render_optional_provider_data_fetch_report(run_optional_provider_data_fetch())

    assert "provider_integration_not_implemented" in report
    assert "api_key" not in report.lower()
