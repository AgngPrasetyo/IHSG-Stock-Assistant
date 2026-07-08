"""Offline tests for Flask routes."""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_ENABLE_API", "false")
    app = create_app({"TESTING": True})
    return app.test_client()


def test_create_app_exists():
    assert create_app({"TESTING": True}) is not None


def test_index_route_ok(client):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Analisis teknikal saham" in html
    assert "Fitur utama" in html
    assert "Tentang sistem" in html


def test_api_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_api_analyze_valid_bbca(client):
    response = client.post("/api/analyze", json={"query": "Analisis saham BBCA"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["analysis"]["ticker"] == "BBCA"
    assert body["analysis"]["sector"] == "Finansial"
    assert body["analysis"]["wfa_config"]["evaluation_horizons"] == [1, 3, 5, 10]
    assert body["explanation"]
    assert body["llm"]
    assert body["analysis"]["technical_hint"]["indicator"] == body["analysis"]["best_indicator"]


def test_api_analyze_valid_ticker_field(client):
    response = client.post("/api/analyze", json={"ticker": "GOTO"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["analysis"]["ticker"] == "GOTO"


def test_api_analyze_alias_bank_bca(client):
    response = client.post("/api/analyze", json={"query": "analisis bank bca"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["analysis"]["ticker"] == "BBCA"


def test_api_analyze_alias_bank_mandiri(client):
    response = client.post("/api/analyze", json={"query": "analisis bank mandiri"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["analysis"]["ticker"] == "BMRI"


def test_api_analyze_empty_json(client):
    response = client.post("/api/analyze", json={})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_api_analyze_non_json(client):
    response = client.post("/api/analyze", data="Analisis saham BBCA", content_type="text/plain")

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_api_analyze_unknown_ticker(client):
    response = client.post("/api/analyze", json={"query": "Analisis saham ABCDXYZ"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["analysis"]
    assert body["llm"]
    assert body["explanation"]


def test_api_stocks_ok(client):
    response = client.get("/api/stocks")
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 40
    assert all("stock_name" in item for item in body["data"])
    assert any(item["ticker"] == "BBCA" and item["stock_name"] == "Bank Central Asia" for item in body["data"])


def test_api_report_pdf_valid_payload(client):
    analyze_response = client.post("/api/analyze", json={"query": "Analisis saham BBCA"})
    analyze_body = analyze_response.get_json()
    payload = {
        "analysis": analyze_body["analysis"],
        "explanation": analyze_body["explanation"],
    }

    response = client.post("/api/report/pdf", json=payload)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")


def test_api_report_pdf_invalid_payload(client):
    response = client.post("/api/report/pdf", json={"analysis": {"success": False}})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_api_sectors_ok(client):
    response = client.get("/api/sectors")
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    sectors = {item["sektor"] for item in body["data"]}
    assert {"Energi", "Finansial", "Industri", "Teknologi"}.issubset(sectors)


def test_routes_do_not_expose_api_key(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-for-users")
    responses = [
        client.get("/api/health"),
        client.get("/api/stocks"),
        client.post("/api/analyze", json={"query": "Analisis saham BBCA"}),
    ]

    for response in responses:
        assert "OPENAI_API_KEY" not in response.get_data(as_text=True)
        assert "sk-proj" not in response.get_data(as_text=True)


def test_analyze_route_uses_llm_service(client, monkeypatch):
    expected = {
        "success": True,
        "message": "Analisis berhasil.",
        "analysis": {"ticker": "TEST", "sector": "Teknologi"},
        "llm": {"provider": "deterministic"},
        "explanation": "Penjelasan hasil analisis teknikal.",
    }
    monkeypatch.setattr("routes.api_routes.llm_service.explain_stock_analysis", lambda value: expected)

    response = client.post("/api/analyze", json={"ticker": "TEST"})

    assert response.status_code == 200
    assert response.get_json() == expected
