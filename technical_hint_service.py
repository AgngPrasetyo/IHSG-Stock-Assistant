"""Deterministic explanations for technical indicator terms."""

from __future__ import annotations

from typing import Any


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
                "description": "Muncul ketika SMA20 memotong SMA50 dari bawah ke atas.",
            },
            {
                "term": "SELL",
                "description": "Muncul ketika SMA20 memotong SMA50 dari atas ke bawah.",
            },
            {
                "term": "HOLD",
                "description": "Muncul ketika belum ada crossover baru yang membentuk sinyal BUY atau SELL.",
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
                "description": "Pada aturan sistem, sinyal BUY muncul saat kondisi RSI memenuhi aturan keluar dari area ekstrem sesuai filter tren.",
            },
            {
                "term": "SELL",
                "description": "Pada aturan sistem, sinyal SELL muncul saat kondisi RSI memenuhi aturan keluar dari area ekstrem sesuai filter tren.",
            },
            {
                "term": "HOLD",
                "description": "Muncul ketika RSI belum membentuk sinyal BUY atau SELL aktif.",
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
                "description": "Muncul ketika MACD Line memotong Signal Line dari bawah ke atas sesuai aturan sistem.",
            },
            {
                "term": "SELL",
                "description": "Muncul ketika MACD Line memotong Signal Line dari atas ke bawah sesuai aturan sistem.",
            },
            {
                "term": "HOLD",
                "description": "Muncul ketika belum ada crossover MACD yang membentuk sinyal BUY atau SELL aktif.",
            },
        ],
    },
}


def get_indicator_hint(indicator_name: str) -> dict[str, Any]:
    """Return deterministic glossary items for the selected best indicator."""
    key = str(indicator_name or "").strip().casefold()
    hint = _HINTS.get(key)
    if hint is None:
        return {"title": "Hint istilah teknikal", "indicator": str(indicator_name or ""), "items": []}

    return {
        "title": hint["title"],
        "indicator": hint["indicator"],
        "items": [item.copy() for item in hint["items"]],
    }
