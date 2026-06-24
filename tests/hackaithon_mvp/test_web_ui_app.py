from pathlib import Path

from fastapi.testclient import TestClient

from src.hackaithon_mvp.web_ui.app import create_app


def _client() -> TestClient:
    return TestClient(create_app(repo_root=Path(".")))


def test_health_endpoint_local_only_flags():
    response = _client().get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "status": "ok",
        "local_only": True,
        "live_data": False,
        "provider_calls": False,
        "trading_output": False,
        "human_review_required": True,
    }


def test_ui_html_renders_core_product_and_evidence():
    response = _client().get("/")

    assert response.status_code == 200
    html = response.text
    assert "VSEF" in html
    assert "Vietcombank Stock Evaluation Framework" in html
    assert "77,850" in html
    assert "forecast_release_blocked_below_60pct" in html
    assert "Within a bounded VN30 hourly absolute-direction benchmark" in html
    assert "61.61% final accuracy over 4,074 rows" in html


def test_ui_html_does_not_contain_action_labels_or_overclaims():
    html = _client().get("/").text

    for forbidden in ("BUY", "SELL", "HOLD"):
        assert forbidden not in html
    assert "production-ready" not in html
    assert "production ready" not in html.lower()
    assert "VSEF predicts stocks with 61" not in html
    assert "forecasts all stocks at 61" not in html


def test_api_summary_and_modules_are_available():
    client = _client()

    summary = client.get("/api/summary")
    flow = client.get("/api/proposal-flow")
    stock = client.get("/api/demo-stock?ticker=VCB")
    modules = client.get("/api/modules")

    assert summary.status_code == 200
    assert flow.status_code == 200
    assert stock.status_code == 200
    assert modules.status_code == 200
    assert summary.json()["engine_universe"]["generated_specs"] == 77850
    assert flow.json()["local_only"] is True
    assert stock.json()["ticker"] == "VCB"
    assert modules.json()["provider_calls"] is False


def test_static_assets_render():
    client = _client()

    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/mock_data.js").status_code == 200
