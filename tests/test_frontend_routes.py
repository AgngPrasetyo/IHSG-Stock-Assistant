"""Tests for the public landing and analysis frontend pages."""

from app import create_app


def test_landing_page_has_explanation_and_no_dashboard_form():
    client = create_app({"TESTING": True}).test_client()
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    for phrase in ("Asisten Pendukung Keputusan Saham", "Memahami sinyal saham, dengan konteks yang jelas.", "Cara Sistem Membaca Saham", "Transparansi"):
        assert phrase in html
    assert 'href="/analysis"' in html
    assert 'id="analysis-form"' not in html
    assert "sk-proj" not in html
    assert "OPENAI_API_KEY" not in html


def test_analysis_page_has_chat_first_input_and_static_assets():
    client = create_app({"TESTING": True}).test_client()
    response = client.get("/analysis")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Halo, saham apa yang ingin Anda analisis?" in html
    assert 'id="analysis-form"' in html
    assert 'id="stock-query"' in html
    assert 'id="stock-select"' in html
    assert 'aria-label="Kirim analisis"' in html
    assert 'workspace-mark' not in html
    assert "sk-proj" not in html
    assert "OPENAI_API_KEY" not in html
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200



