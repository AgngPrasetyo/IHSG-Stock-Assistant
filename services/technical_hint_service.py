"""Deterministic explanations for technical indicator terms."""
# ================================================================
# CATATAN FILE:
# File ini menyimpan penjelasan istilah indikator dan metrik evaluasi secara deterministik. Data dari file ini digunakan untuk menampilkan hint atau glossary pada dashboard dan laporan.
# Catatan ini ditambahkan untuk membantu penjelasan kode saat sidang.
# Bagian di bawah ini tidak mengubah logika program; hanya berupa komentar dokumentasi.
# ================================================================


from __future__ import annotations

from typing import Any


METRIC_ITEMS: list[dict[str, str]] = [
    {
        "term": "Directional Accuracy",
        "description": (
            "Persentase kecocokan seluruh sinyal BUY/SELL terhadap arah harga "
            "berdasarkan Average Forward Return pada T+1, T+3, T+5, dan T+10 "
            "hari perdagangan bursa saham. Metrik ini digunakan untuk menentukan indikator terbaik."
        ),
    },
    {
    "term": "Average Forward Return",
    "description": (
        "Rata-rata return harga setelah sinyal pada T+1, T+3, T+5, dan T+10 "
        "hari perdagangan bursa saham. Nilai ini digunakan untuk menilai apakah "
        "arah sinyal BUY atau SELL sesuai secara historis."
    ),
    },
    {
        "term": "Hit Rate",
        "description": (
            "Rata-rata keberhasilan sinyal BUY/SELL yang muncul pada setiap periode evaluasi."
        ),
    },
    {
        "term": "Total Active Signals",
        "description": "Jumlah seluruh sinyal BUY dan SELL yang dievaluasi.",
    },
    {
        "term": "Correct Signals",
        "description": (
            "Jumlah sinyal BUY dan SELL yang sesuai berdasarkan Average Forward Return "
            "pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham."
        ),
    },
]


_HINTS: dict[str, dict[str, Any]] = {
    "ma crossover": {
    "title": "Hint istilah MA Crossover",
    "indicator": "MA Crossover",
    "items": [
        {
            "term": "MA Crossover",
            "description": "Metode yang membaca perpotongan dua rata-rata harga.",
        },
        {
            "term": "SMA10",
            "description": "Rata-rata harga penutupan 10 hari perdagangan terakhir.",
        },
        {
            "term": "SMA50",
            "description": "Rata-rata harga penutupan 50 hari perdagangan terakhir.",
        },
        {
            "term": "BUY",
            "description": "Muncul saat SMA10 memotong SMA50 dari bawah ke atas.",
        },
        {
            "term": "SELL",
            "description": "Muncul saat SMA10 memotong SMA50 dari atas ke bawah.",
        },
        {
            "term": "HOLD",
            "description": "Muncul saat tidak ada sinyal BUY atau SELL baru pada data terakhir.",
        },
    ],
},
    "rsi": {
    "title": "Hint istilah RSI",
    "indicator": "RSI",
    "items": [
        {
            "term": "RSI",
            "description": "Indikator momentum yang membaca kekuatan pergerakan harga pada skala 0 sampai 100.",
        },
        {
        "term": "Overbought",
        "description": "Kondisi ketika RSI berada di atas level 70 dan sistem menunggu RSI turun keluar dari area tersebut untuk membaca sinyal SELL.",
        },
        {
        "term": "Oversold",
        "description": "Kondisi ketika RSI berada di bawah level 30 dan sistem menunggu RSI naik keluar dari area tersebut untuk membaca sinyal BUY.",
        },
        {
            "term": "BUY",
            "description": "Muncul saat RSI keluar dari area oversold sesuai aturan sistem.",
        },
        {
            "term": "SELL",
            "description": "Muncul saat RSI keluar dari area overbought sesuai aturan sistem.",
        },
        {
            "term": "HOLD",
            "description": "Muncul saat kondisi BUY atau SELL belum terpenuhi pada data terakhir.",
        },
    ],
},
    "macd": {
    "title": "Hint istilah MACD",
    "indicator": "MACD",
    "items": [
        {
            "term": "MACD",
            "description": "Indikator momentum yang membaca hubungan antara garis MACD dan garis sinyal.",
        },
        {
            "term": "MACD Line",
            "description": "Garis utama MACD yang menunjukkan perubahan momentum harga.",
        },
        {
            "term": "Signal Line",
            "description": "Garis pembanding yang digunakan untuk membaca perubahan sinyal MACD.",
        },
        {
            "term": "BUY",
            "description": "Muncul saat MACD Line memotong Signal Line dari bawah ke atas.",
        },
        {
            "term": "SELL",
            "description": "Muncul saat MACD Line memotong Signal Line dari atas ke bawah.",
        },
        {
            "term": "HOLD",
            "description": "Muncul saat tidak ada sinyal BUY atau SELL baru pada data terakhir.",
        },
    ],
},
}



# CATATAN FUNGSI: Mengambil hint istilah teknikal dan metrik evaluasi berdasarkan indikator terbaik.
# CARA KERJA SINGKAT: Mencocokkan nama indikator ke daftar hint, lalu mengembalikan salinan item agar data asli tidak berubah.
# KEGUNAAN: Menyediakan glossary untuk dashboard dan laporan PDF.
def get_indicator_hint(indicator_name: str) -> dict[str, Any]:
    """Return deterministic glossary items for the selected best indicator."""
    key = str(indicator_name or "").strip().casefold()
    hint = _HINTS.get(key)
    if hint is None:
        return {
            "title": "Hint istilah teknikal",
            "indicator": str(indicator_name or ""),
            "items": [],
            "metric_items": [item.copy() for item in METRIC_ITEMS],
        }

    return {
        "title": hint["title"],
        "indicator": hint["indicator"],
        "items": [item.copy() for item in hint["items"]],
        "metric_items": [item.copy() for item in METRIC_ITEMS],
    }
