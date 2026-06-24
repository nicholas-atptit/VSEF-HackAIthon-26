from src.hackaithon_mvp.optional_vn_market_data_adapter import (
    inspect_vn_market_data_config,
    render_optional_vn_market_data_report,
    run_optional_vn_market_data_expansion,
)


def test_adapter_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOW_PROVIDER_DATA_FETCH", raising=False)

    result = run_optional_vn_market_data_expansion(output_root=str(tmp_path / ".tmp_real_expanded_60pct" / "data"))
    report = render_optional_vn_market_data_report(result)

    assert result["data_expansion_status"] == "disabled"
    assert result["expanded_data_available"] is False
    assert "Provider fetch enabled: False" in report
    assert "provider_fetch_disabled_by_default" in result["provider_gaps"]


def test_adapter_requires_explicit_env_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ALLOW_PROVIDER_DATA_FETCH", "1")
    monkeypatch.delenv("DATA_PROVIDER", raising=False)

    result = run_optional_vn_market_data_expansion(output_root=str(tmp_path / ".tmp_real_expanded_60pct" / "data"))

    assert result["data_expansion_status"] == "missing_required_env"
    assert "DATA_PROVIDER" in result["missing_required_env"]


def test_config_redacts_secret_like_values(monkeypatch):
    monkeypatch.setenv("DATA_PROVIDER", "vnstock")
    monkeypatch.setenv("START_DATE", "2020-01-01")
    monkeypatch.setenv("END_DATE", "2026-06-01")
    monkeypatch.setenv("MAX_TICKERS", "35")
    monkeypatch.setenv("OUTPUT_ROOT", ".tmp_real_expanded_60pct/data")
    monkeypatch.setenv("API_KEY", "secret")

    result = inspect_vn_market_data_config(output_root=".tmp_real_expanded_60pct/data")

    assert result["config"]["DATA_PROVIDER"] == "vnstock"
    assert result["config"]["MAX_TICKERS"] == 35
