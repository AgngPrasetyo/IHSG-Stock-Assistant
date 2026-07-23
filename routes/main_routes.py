"""Public non-API routes."""

# CATATAN FILE:
# File ini berisi route halaman publik non-API.
# Kegunaannya adalah menampilkan halaman landing dan halaman analisis utama kepada pengguna.


from __future__ import annotations

from typing import Any

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


# CATATAN FUNGSI: Membuat pratinjau analisis untuk halaman landing.
# CARA KERJA SINGKAT: Fungsi mencoba analisis BBCA dan memakai fallback jika gagal.
# KEGUNAAN: Dipakai agar landing page tetap tampil meskipun data analisis tidak tersedia.
def _build_landing_preview() -> dict[str, Any]:
    """Build adaptive homepage preview from deterministic BBCA analysis."""
    fallback = {
        "ticker": "BBCA",
        "stock_name": "Bank Central Asia",
        "sector": "Finansial",
        "latest_signal": "HOLD",
        "best_indicator": "MA Crossover",
        "directional_accuracy": "51.92%",
        "evaluation_label": "T+1 · T+3 · T+5 · T+10",
    }

    try:
        from services.analysis_service import analyze_stock

        analysis = analyze_stock("BBCA")
        if not analysis.get("success"):
            return fallback

        metrics = analysis.get("metrics") or {}
        accuracy = metrics.get("directional_accuracy")
        wfa_config = analysis.get("wfa_config") or {}

        evaluation_label = str(
            wfa_config.get("evaluation_horizon_label")
            or "T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham"
        )
        evaluation_label = (
            evaluation_label.replace(", ", " · ")
            .replace("dan ", "")
            .replace(" hari perdagangan bursa saham", "")
        )

        return {
            "ticker": analysis.get("ticker") or fallback["ticker"],
            "stock_name": analysis.get("stock_name") or fallback["stock_name"],
            "sector": analysis.get("sector") or fallback["sector"],
            "latest_signal": analysis.get("latest_signal") or fallback["latest_signal"],
            "best_indicator": analysis.get("best_indicator") or fallback["best_indicator"],
            "directional_accuracy": (
                f"{float(accuracy):.2f}%"
                if accuracy is not None
                else fallback["directional_accuracy"]
            ),
            "evaluation_label": evaluation_label or fallback["evaluation_label"],
        }
    except Exception:
        return fallback


@main_bp.get("/")
# CATATAN FUNGSI: Menampilkan halaman utama aplikasi.
# CARA KERJA SINGKAT: Preview dibangun lalu dikirim ke template index.
# KEGUNAAN: Dipakai untuk route root aplikasi.
def index() -> str:
    """Render the public landing page with an adaptive analysis preview."""
    preview = _build_landing_preview()
    return render_template("index.html", preview=preview)


@main_bp.get("/analysis")
# CATATAN FUNGSI: Menampilkan halaman analisis saham.
# CARA KERJA SINGKAT: Template analysis.html dirender tanpa proses analisis langsung.
# KEGUNAAN: Dipakai untuk halaman kerja utama pengguna.
def analysis() -> str:
    """Render the focused stock analysis experience."""
    return render_template("analysis.html")