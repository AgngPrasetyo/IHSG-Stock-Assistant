"""JSON API routes that connect requests to the existing service layer."""

# CATATAN FILE:
# File ini berisi route API berbasis Flask untuk frontend.
# Kegunaannya adalah menghubungkan request dari pengguna dengan service analisis, daftar saham/sektor, health check, dan pembuatan laporan PDF.


from __future__ import annotations

from io import BytesIO
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from services import llm_service
from services.mapping_service import load_mapping
from services.report_service import build_analysis_pdf

api_bp = Blueprint("api", __name__, url_prefix="/api")


# CATATAN FUNGSI: Membentuk respons JSON yang konsisten untuk endpoint API.
# CARA KERJA SINGKAT: Payload dikirim bersama status code Flask.
# KEGUNAAN: Merapikan format respons frontend.
def response_json(payload: dict[str, Any], status_code: int = 200):
    """Return a consistent JSON response from API endpoints."""
    return jsonify(payload), status_code


@api_bp.get("/health")
# CATATAN FUNGSI: Memeriksa kondisi dasar backend.
# CARA KERJA SINGKAT: Endpoint mengembalikan status ok tanpa menjalankan analisis berat.
# KEGUNAAN: Dipakai untuk memastikan service API hidup.
def health():
    """Return a lightweight backend health payload."""
    return response_json({
        "success": True,
        "status": "ok",
        "service": "stock_decision_assistant",
        "stage": "flask_routes",
    })


@api_bp.get("/stocks")
# CATATAN FUNGSI: Mengirim daftar saham yang tersedia ke frontend.
# CARA KERJA SINGKAT: Mapping dibaca dan hanya kolom publik yang dikirim.
# KEGUNAAN: Dipakai untuk dropdown atau daftar saham.
def stocks():
    """Return public stock dropdown data without exposing sensitive fields."""
    try:
        mapping_df = load_mapping()
        columns = ["ticker", "ticker_yfinance", "sektor", "stock_name"]
        data = mapping_df.loc[:, columns].to_dict(orient="records")
        return response_json({"success": True, "data": data})
    except Exception:
        return _server_error()


@api_bp.get("/sectors")
# CATATAN FUNGSI: Mengirim jumlah saham per sektor.
# CARA KERJA SINGKAT: Mapping dihitung berdasarkan kolom sektor dan diurutkan.
# KEGUNAAN: Dipakai untuk informasi ringkas cakupan sektor.
def sectors():
    """Return sector counts from the current stock mapping."""
    try:
        mapping_df = load_mapping()
        counts = mapping_df["sektor"].value_counts().sort_index()
        data = [
            {"sektor": str(sector), "jumlah_saham": int(count)}
            for sector, count in counts.items()
        ]
        return response_json({"success": True, "data": data})
    except Exception:
        return _server_error()


@api_bp.post("/analyze")
# CATATAN FUNGSI: Menerima request analisis saham dari frontend.
# CARA KERJA SINGKAT: Fungsi memvalidasi JSON, mengambil query/ticker, lalu memanggil service LLM dan analisis.
# KEGUNAAN: Menjadi endpoint utama saat user menekan analisis.
def analyze():
    """Analyze a user query or ticker through the service layer."""
    if not request.is_json:
        return response_json({
            "success": False,
            "message": "Request harus menggunakan JSON.",
        }, 400)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return response_json({
            "success": False,
            "message": "Body JSON harus berupa object.",
        }, 400)

    query = str(payload.get("query") or "").strip()
    ticker = str(payload.get("ticker") or "").strip()
    user_input = query or ticker
    if not user_input:
        return response_json({
            "success": False,
            "message": "Input analisis saham belum tersedia.",
        }, 400)

    try:
        result = llm_service.explain_stock_analysis(user_input)
        return response_json(result)
    except Exception:
        return _server_error()


@api_bp.post("/report/pdf")
# CATATAN FUNGSI: Membuat laporan PDF dari payload analisis frontend.
# CARA KERJA SINGKAT: Payload divalidasi, PDF dibangun, lalu dikirim sebagai file download.
# KEGUNAAN: Dipakai untuk fitur ekspor laporan analisis.
def report_pdf():
    """Build a PDF report from a frontend-provided analysis payload."""
    if not request.is_json:
        return response_json({
            "success": False,
            "message": "Request harus menggunakan JSON.",
        }, 400)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return response_json({
            "success": False,
            "message": "Body JSON harus berupa object.",
        }, 400)

    try:
        pdf_bytes = build_analysis_pdf(payload)
    except ValueError:
        return response_json({
            "success": False,
            "message": "Payload laporan tidak valid.",
        }, 400)
    except Exception:
        return _server_error()

    analysis = payload.get("analysis") or {}
    ticker = _safe_filename_part(analysis.get("ticker") or "saham")
    latest_date = _safe_filename_part(analysis.get("latest_date") or "terbaru")
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"laporan-analisis-{ticker}-{latest_date}.pdf",
    )


@api_bp.app_errorhandler(500)
# CATATAN FUNGSI: Menangani error server agar detail internal tidak bocor.
# CARA KERJA SINGKAT: Error 500 diarahkan ke respons generik.
# KEGUNAAN: Menjaga keamanan dan kerapian pesan API.
def handle_api_server_error(_error: Exception):
    """Prevent server internals from being exposed through API responses."""
    return _server_error()


# CATATAN FUNGSI: Membersihkan teks agar aman menjadi nama file.
# CARA KERJA SINGKAT: Hanya karakter alfanumerik, strip, dan underscore yang dipertahankan.
# KEGUNAAN: Dipakai saat memberi nama file PDF.
def _safe_filename_part(value: Any) -> str:
    """Return a conservative filename segment for generated reports."""
    text = str(value or "").strip()
    safe = "".join(char for char in text if char.isalnum() or char in {"-", "_"})
    return safe or "saham"


# CATATAN FUNGSI: Membentuk respons error server generik.
# CARA KERJA SINGKAT: Fungsi mengembalikan success false dengan status 500.
# KEGUNAAN: Mencegah detail exception tampil ke pengguna.
def _server_error():
    """Return the generic API server error payload."""
    return response_json({
        "success": False,
        "message": "Terjadi kesalahan pada server.",
    }, 500)
