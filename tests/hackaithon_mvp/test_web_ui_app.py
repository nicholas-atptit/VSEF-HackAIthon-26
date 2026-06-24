from pathlib import Path

from fastapi.testclient import TestClient

from src.hackaithon_mvp.web_ui.app import create_app


def _client(repo_root: Path | str = Path(".")) -> TestClient:
    return TestClient(create_app(repo_root=repo_root))


def _blocked_action_words() -> tuple[str, str, str]:
    return ("B" + "UY", "S" + "ELL", "H" + "OLD")


def _blocked_overclaim_words() -> tuple[str, str, str, str]:
    return (
        "production" + "-ready",
        "production " + "ready",
        "target " + "price",
        "trading " + "signal",
    )


def _blocked_broad_claims() -> tuple[str, str]:
    return ("VSEF predicts stocks with " + "61", "forecasts all stocks at " + "61")


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


def test_vn30_endpoint_returns_exactly_30_tickers():
    response = _client().get("/api/vn30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker_count"] == 30
    assert len(payload["cards"]) == 30
    assert payload["local_only"] is True
    assert payload["live_data"] is False
    assert payload["provider_calls"] is False


def test_ticker_command_and_report_endpoints_work():
    client = _client()

    ticker = client.get("/api/ticker/VCB")
    command = client.get("/api/terminal-command?cmd=VCB%20DIAG")
    report = client.get("/api/report-preview?ticker=VCB")

    assert ticker.status_code == 200
    assert command.status_code == 200
    assert report.status_code == 200
    assert ticker.json()["ticker"] == "VCB"
    assert command.json()["command_status"] == "completed"
    assert command.json()["payload"]["mode"] == "DIAG"
    assert report.json()["writes_files_by_default"] is False


def test_ui_html_renders_terminal_evidence():
    response = _client().get("/")

    assert response.status_code == 200
    html = response.text
    assert "VSEF Terminal" in html
    assert "VN30" in html
    assert "77,850" in html
    assert "61.61%" in html
    assert "forecast_release_blocked_below_60pct" in html
    assert "60% GATE BLOCKED" in html
    assert "Within a bounded VN30 hourly absolute-direction benchmark" in html
    assert "BENCHMARK SCOPE LOCKED" in html


def test_ui_html_does_not_contain_action_labels_or_overclaims():
    html = _client().get("/").text

    for forbidden in _blocked_action_words():
        assert forbidden not in html
    for forbidden in _blocked_overclaim_words():
        assert forbidden not in html.lower()
    for forbidden in _blocked_broad_claims():
        assert forbidden not in html


def test_social_and_rag_placeholders_are_labeled_demo_local_no_live():
    html = _client().get("/").text

    assert "demo placeholder" in html
    assert "local demo" in html
    assert "no live scraping" in html
    assert "no live provider call" in html
    assert "No real LLM call" not in html
    assert "cannot mutate models" in html


def test_endpoints_do_not_write_files_by_default(tmp_path):
    client = _client(repo_root=tmp_path)

    assert client.get("/api/vn30").status_code == 200
    assert client.get("/api/ticker/VCB").status_code == 200
    assert client.get("/api/terminal-command?cmd=GATE").status_code == 200
    assert client.get("/api/report-preview?ticker=VCB").status_code == 200
    assert not (tmp_path / ".tmp_web_ui_demo").exists()


def test_static_assets_render():
    client = _client()

    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/mock_data.js").status_code == 200
