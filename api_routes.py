"""JSON API routes that connect requests to the existing service layer."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from services import llm_service
from services.mapping_service import load_mapping
from services.report_service import build_analysis_pdf

api_bp = Blueprint("api", __name__, url_prefix="/api")


def response_json(payload: dict[str, Any], status_code: int = 200):
    """Return a consistent JSON response from API endpoints."""
    return jsonify(payload), status_code


@api_bp.get("/health")
def health():
    """Return a lightweight backend health payload."""
    return response_json({
        "success": True,
        "status": "ok",
        "service": "stock_decision_assistant",
        "stage": "flask_routes",
    })


@api_bp.get("/stocks")
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
def handle_api_server_error(_error: Exception):
    """Prevent server internals from being exposed through API responses."""
    return _server_error()


def _safe_filename_part(value: Any) -> str:
    """Return a conservative filename segment for generated reports."""
    text = str(value or "").strip()
    safe = "".join(char for char in text if char.isalnum() or char in {"-", "_"})
    return safe or "saham"


def _server_error():
    """Return the generic API server error payload."""
    return response_json({
        "success": False,
        "message": "Terjadi kesalahan pada server.",
    }, 500)
