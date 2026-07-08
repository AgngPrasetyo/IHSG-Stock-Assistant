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
            "best_indicator": "MACD",
            "latest_signal": "HOLD",
            "latest_condition": "MACD Line 12.00; Signal Line 12.40; Histogram -0.40. Sinyal HOLD karena tidak ada crossover baru antara MACD Line dan Signal Line pada data terakhir.",
            "latest_date": "2026-06-22",
            "latest_close": 9000,
            "metrics": {
                "directional_accuracy": 50.65,
                "hit_rate": 54.64,
                "total_active_signals": 154,
                "correct_signals": 78,
            },
            "indicator_comparison": [
                {
                    "indicator": "MA Crossover",
                    "directional_accuracy": 45.0,
                    "hit_rate": 45.0,
                    "total_active_signals": 10,
                    "correct_signals": 5,
                },
                {
                    "indicator": "MACD",
                    "directional_accuracy": 50.65,
                    "hit_rate": 54.64,
                    "total_active_signals": 154,
                    "correct_signals": 78,
                },
                {
                    "indicator": "RSI",
                    "directional_accuracy": 40.0,
                    "hit_rate": 40.0,
                    "total_active_signals": 12,
                    "correct_signals": 5,
                },
            ],
            "post_signal_validation": [
                {
                    "horizon": 1,
                    "label": "T+1",
                    "signal_date": "2026-06-22",
                    "target_date": None,
                    "signal": "HOLD",
                    "return_pct": None,
                    "status": "NOT_EVALUATED_HOLD",
                    "message": "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif.",
                },
                {
                    "horizon": 3,
                    "label": "T+3",
                    "signal_date": "2026-06-22",
                    "target_date": None,
                    "signal": "HOLD",
                    "return_pct": None,
                    "status": "NOT_EVALUATED_HOLD",
                    "message": "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif.",
                },
                {
                    "horizon": 5,
                    "label": "T+5",
                    "signal_date": "2026-06-22",
                    "target_date": None,
                    "signal": "HOLD",
                    "return_pct": None,
                    "status": "NOT_EVALUATED_HOLD",
                    "message": "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif.",
                },
                {
                    "horizon": 10,
                    "label": "T+10",
                    "signal_date": "2026-06-22",
                    "target_date": None,
                    "signal": "HOLD",
                    "return_pct": None,
                    "status": "NOT_EVALUATED_HOLD",
                    "message": "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif.",
                },
            ],
            "technical_hint": get_indicator_hint("MACD"),
            "disclaimer": "Hasil ini merupakan sinyal analisis teknikal, bukan rekomendasi investasi final.",
        },
        "explanation": "Penjelasan hasil analisis teknikal dari payload yang sudah tersedia. Evaluasi menggunakan Average Forward Return pada T+1, T+3, T+5, dan T+10.",
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
    assert b"MACD" in pdf
    assert b"T+10" in pdf


def test_build_analysis_pdf_handles_mixed_post_signal_validation_statuses():
    payload = sample_payload()
    payload["analysis"]["post_signal_validation"] = [
        {
            "horizon": 1,
            "label": "T+1",
            "signal": "BUY",
            "signal_date": "2026-06-22",
            "target_date": "2026-06-23",
            "return_pct": 3.264,
            "status": "MATCH",
            "message": "Pergerakan Close pada T+1 searah dengan sinyal BUY.",
        },
        {
            "horizon": 3,
            "label": "T+3",
            "signal": "HOLD",
            "signal_date": "2026-06-22",
            "target_date": None,
            "return_pct": None,
            "status": "NOT_EVALUATED_HOLD",
            "message": "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif.",
        },
        {
            "horizon": 5,
            "label": "T+5",
            "signal": "SELL",
            "signal_date": "2026-06-22",
            "target_date": None,
            "return_pct": float("nan"),
            "status": "UNAVAILABLE",
            "message": "Data setelah tanggal sinyal belum tersedia untuk horizon ini.",
        },
        {
            "horizon": 10,
            "label": "T+10",
            "signal": "SELL",
            "signal_date": "2026-06-22",
            "target_date": None,
            "return_pct": None,
            "status": "UNAVAILABLE",
            "message": "Data setelah tanggal sinyal belum tersedia untuk horizon ini.",
        },
    ]

    pdf = build_analysis_pdf(payload)

    assert pdf.startswith(b"%PDF")
    assert b"Validasi Lanjutan Sinyal Terbaru" in pdf
    assert b"Sesuai" in pdf
    assert b"arah" in pdf
    assert b"T+10" in pdf
    assert b"Paragraph(" not in pdf
    assert b"caseSensitive" not in pdf
    assert b"NOT_EVALUATED_HOLD" not in pdf
    assert b"NaN" not in pdf


def test_build_analysis_pdf_sanitizes_invalid_box_characters_in_explanation():
    payload = sample_payload()
    payload["explanation"] = "MA Crossover, ■■■■■■ menghasilkan sinyal BUY aktif."

    pdf = build_analysis_pdf(payload)

    assert pdf.startswith(b"%PDF")
    assert "■".encode("utf-8") not in pdf
    assert b"Paragraph(" not in pdf
    assert b"caseSensitive" not in pdf
