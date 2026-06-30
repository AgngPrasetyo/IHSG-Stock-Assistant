import pytest

from services.report_service import build_analysis_pdf
from services.technical_hint_service import get_indicator_hint


def sample_payload():
    return {
        "analysis": {
            "success": True,
            "message": "Analisis berhasil.",
            "ticker": "BBCA",
            "ticker_yfinance": "BBCA.JK",
            "stock_name": "Bank Central Asia",
            "sector": "Finansial",
            "best_indicator": "MA Crossover",
            "latest_signal": "HOLD",
            "latest_condition": "Close 9000.00; SMA20 8950.00; SMA50 8800.00.",
            "latest_date": "2026-06-22",
            "latest_close": 9000,
            "metrics": {
                "directional_accuracy": 58.25,
                "hit_rate": 60.0,
                "total_active_signals": 12,
                "correct_signals": 7,
            },
            "indicator_comparison": [
                {
                    "indicator": "MA Crossover",
                    "directional_accuracy": 58.25,
                    "hit_rate": 60.0,
                    "total_active_signals": 12,
                    "correct_signals": 7,
                },
                {
                    "indicator": "MACD",
                    "directional_accuracy": 50.0,
                    "hit_rate": 50.0,
                    "total_active_signals": 10,
                    "correct_signals": 5,
                },
            ],
            "technical_hint": get_indicator_hint("MA Crossover"),
            "disclaimer": "Hasil ini merupakan sinyal analisis teknikal, bukan rekomendasi investasi final.",
        },
        "explanation": "Penjelasan hasil analisis teknikal dari payload yang sudah tersedia.",
    }


def test_build_analysis_pdf_valid_payload_returns_pdf_bytes():
    pdf = build_analysis_pdf(sample_payload())

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


def test_build_analysis_pdf_invalid_payload_raises_value_error():
    with pytest.raises(ValueError):
        build_analysis_pdf({"analysis": {"success": False}})


def test_build_analysis_pdf_uses_payload_without_rerunning_analysis(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("report_service must not run analysis service")

    monkeypatch.setattr("services.analysis_service.analyze_stock", fail_if_called)

    pdf = build_analysis_pdf(sample_payload())

    assert pdf.startswith(b"%PDF")

def test_build_analysis_pdf_does_not_render_paragraph_object_dump():
    pdf = build_analysis_pdf(sample_payload())

    assert b"Paragraph(" not in pdf
    assert b"caseSensitive" not in pdf


def test_build_analysis_pdf_contains_key_plain_values_when_stable():
    pdf = build_analysis_pdf(sample_payload())

    assert b"Stock Decision Assistant" in pdf
    assert b"Laporan Hasil Analisis Teknikal Saham" in pdf
    assert b"BBCA" in pdf
    assert b"Bank Central Asia" in pdf
    assert b"MA Crossover" in pdf


