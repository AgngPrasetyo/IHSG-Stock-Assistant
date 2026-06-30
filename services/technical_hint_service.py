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
                "description": "Kondisi ketika RSI berada di atas 70.",
            },
            {
                "term": "Oversold",
                "description": "Kondisi ketika RSI berada di bawah 30.",
            },
            {
                "term": "BUY",
                "description": "Muncul saat RSI keluar dari area oversold dan filter tren SMA50 terpenuhi. RSI yang masih oversold belum otomatis BUY.",
            },
            {
                "term": "SELL",
                "description": "Muncul saat RSI keluar dari area overbought dan filter tren SMA50 terpenuhi. RSI yang masih overbought belum otomatis SELL.",
            },
            {
                "term": "HOLD",
                "description": "Muncul saat syarat BUY atau SELL belum lengkap, termasuk ketika RSI masih berada di area ekstrem tetapi belum keluar sesuai aturan sistem.",
            },
        ],
    },
    "macd": {
        "title": "Hint istilah MACD",
        "indicator": "MACD",
        "items": [
            {
                "term": "MACD",
                "description": "Indikator momentum yang membandingkan pergerakan rata-rata harga jangka pendek dan jangka panjang.",
            },
            {
                "term": "MACD Line",
                "description": "Garis utama MACD yang menunjukkan perubahan momentum harga.",
            },
            {
                "term": "Signal Line",
                "description": "Garis pembanding untuk membaca perubahan sinyal MACD.",
            },
            {
                "term": "BUY",
                "description": "Muncul saat MACD Line memotong Signal Line dari bawah ke atas dan filter tren SMA50 terpenuhi.",
            },
            {
                "term": "SELL",
                "description": "Muncul saat MACD Line memotong Signal Line dari atas ke bawah dan filter tren SMA50 terpenuhi.",
            },
            {
                "term": "HOLD",
                "description": "Muncul saat tidak ada crossover baru atau filter tren belum terpenuhi.",
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
