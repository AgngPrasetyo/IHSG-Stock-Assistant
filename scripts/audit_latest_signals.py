# scripts/audit_latest_signals.py

from __future__ import annotations

from pathlib import Path
from services.analysis_service import prepare_latest_analysis_dataframe
from services.mapping_service import get_stock_info
from services.signal_service import (
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)
import sys
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))





AUDIT_TICKERS = ["MARK", "BBCA", "ADRO", "GOTO"]

DISPLAY_COLUMNS = [
    "Close",
    "SMA20",
    "SMA50",
    "MACD",
    "MACD_Signal",
    "RSI",
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
]


def fmt(value: object) -> str:
    if pd.isna(value):
        return "NaN"
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def audit_ma_crossover(df: pd.DataFrame) -> dict[str, object]:
    prev = df.iloc[-2]
    latest = df.iloc[-1]

    prev_date = df.index[-2].strftime("%Y-%m-%d")
    latest_date = df.index[-1].strftime("%Y-%m-%d")
    latest_signal = str(latest[MA_CROSSOVER_SIGNAL_COLUMN]).upper()

    buy_valid = (
        pd.notna(prev["SMA20"])
        and pd.notna(prev["SMA50"])
        and pd.notna(latest["SMA20"])
        and pd.notna(latest["SMA50"])
        and prev["SMA20"] <= prev["SMA50"]
        and latest["SMA20"] > latest["SMA50"]
    )

    sell_valid = (
        pd.notna(prev["SMA20"])
        and pd.notna(prev["SMA50"])
        and pd.notna(latest["SMA20"])
        and pd.notna(latest["SMA50"])
        and prev["SMA20"] >= prev["SMA50"]
        and latest["SMA20"] < latest["SMA50"]
    )

    if latest_signal == "BUY" and buy_valid:
        conclusion = "VALID_BUY_CROSSOVER_BARU"
    elif latest_signal == "SELL" and sell_valid:
        conclusion = "VALID_SELL_CROSSOVER_BARU"
    elif latest_signal == "HOLD" and not buy_valid and not sell_valid:
        conclusion = "VALID_HOLD_TIDAK_ADA_CROSSOVER_BARU"
    else:
        conclusion = "PERLU_CEK_LOGIKA_ATAU_DATA"

    return {
        "prev_date": prev_date,
        "prev_sma20": prev["SMA20"],
        "prev_sma50": prev["SMA50"],
        "latest_date": latest_date,
        "latest_sma20": latest["SMA20"],
        "latest_sma50": latest["SMA50"],
        "latest_signal": latest_signal,
        "buy_valid": buy_valid,
        "sell_valid": sell_valid,
        "conclusion": conclusion,
    }


def audit_ticker(ticker: str) -> None:
    print("=" * 90)
    print(f"AUDIT TICKER: {ticker}")

    stock_info = get_stock_info(ticker)
    if not stock_info:
        print("Mapping saham tidak ditemukan.")
        return

    ticker_yfinance = str(stock_info["ticker_yfinance"])
    df = prepare_latest_analysis_dataframe(ticker_yfinance)

    print(f"Ticker yfinance : {ticker_yfinance}")
    print(f"Rows            : {len(df)}")
    print(f"Tanggal awal    : {df.index.min().strftime('%Y-%m-%d')}")
    print(f"Tanggal akhir   : {df.index.max().strftime('%Y-%m-%d')}")
    print()

    print("15 baris terakhir:")
    print(df[DISPLAY_COLUMNS].tail(15).to_string())
    print()

    ma = audit_ma_crossover(df)

    print("Validasi MA Crossover dua baris terakhir:")
    print(f"Tanggal sebelumnya : {ma['prev_date']}")
    print(f"SMA20 sebelumnya   : {fmt(ma['prev_sma20'])}")
    print(f"SMA50 sebelumnya   : {fmt(ma['prev_sma50'])}")
    print(f"Tanggal terbaru    : {ma['latest_date']}")
    print(f"SMA20 terbaru      : {fmt(ma['latest_sma20'])}")
    print(f"SMA50 terbaru      : {fmt(ma['latest_sma50'])}")
    print(f"Sinyal terbaru     : {ma['latest_signal']}")
    print(f"Kesimpulan         : {ma['conclusion']}")
    print()


def main() -> None:
    for ticker in AUDIT_TICKERS:
        audit_ticker(ticker)


if __name__ == "__main__":
    main()