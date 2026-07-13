"""Tests for the public landing and analysis frontend pages."""

from app import create_app


def test_landing_page_has_final_explanation_and_no_dashboard_form():
    client = create_app({"TESTING": True}).test_client()
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    for phrase in (
        "Analisis teknikal saham yang lebih mudah dipahami.",
        "Fitur utama",
        "Dari kode saham menjadi hasil analisis.",
        "Tentang sistem",
    ):
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
    assert 'href="/#tentang-sistem"' in html
    assert 'workspace-mark' not in html
    assert "sk-proj" not in html
    assert "OPENAI_API_KEY" not in html
    assert client.get("/static/css/style.css").status_code == 200
    js_response = client.get("/static/js/main.js")
    assert js_response.status_code == 200
    js_text = js_response.get_data(as_text=True)
    assert "Metrik evaluasi indikator terbaik" in js_text
    assert "Data saham terakhir" in js_text
    