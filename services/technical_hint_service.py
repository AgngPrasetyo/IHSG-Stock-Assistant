"""Deterministic explanations for technical indicator terms."""

from __future__ import annotations

from typing import Any


METRIC_ITEMS: list[dict[str, str]] = [
    {
        "term": "Directional Accuracy",
        "description": "Persentase kecocokan seluruh sinyal aktif BUY/SELL terhadap arah harga setelah 3 trading days.",
    },
    {
        "term": "Hit Rate",
        "description": "Rata-rata persentase keberhasilan sinyal aktif pada setiap window evaluasi.",
    },
    {
        "term": "Total Active Signals",
        "description": "Jumlah seluruh sinyal BUY dan SELL yang dievaluasi.",
    },
    {
        "term": "Correct Signals",
        "description": "Jumlah sinyal BUY dan SELL yang sesuai dengan arah harga setelah 3 trading days.",
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
                "term": "SMA20",
                "description": "Rata-rata harga penutupan 20 hari perdagangan terakhir.",
            },
            {
                "term": "SMA50",
                "description": "Rata-rata harga penutupan 50 hari perdagangan terakhir.",
            },
            {
                "term": "BUY",
                "description": "Muncul saat SMA20 memotong SMA50 dari bawah ke atas.",
            },
            {
                "term": "SELL",
                "description": "Muncul saat SMA20 memotong SMA50 dari atas ke bawah.",
            },
            {
                "term": "HOLD",
                "description": "Muncul saat tidak ada crossover baru pada data terakhir.",
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
            "description": "Kondisi ketika RSI berada pada area tinggi dan harga berpotensi mengalami pelemahan momentum.",
        },
        {
            "term": "Oversold",
            "description": "Kondisi ketika RSI berada pada area rendah dan harga berpotensi mengalami penguatan momentum.",
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
            "description": "Muncul saat MACD Line memotong Signal Line dari bawah ke atas sesuai aturan sistem.",
        },
        {
            "term": "SELL",
            "description": "Muncul saat MACD Line memotong Signal Line dari atas ke bawah sesuai aturan sistem.",
        },
        {
            "term": "HOLD",
            "description": "Muncul saat tidak ada sinyal BUY atau SELL baru pada data terakhir.",
        },
    ],
},
}


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
