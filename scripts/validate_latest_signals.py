# scripts/validate_latest_signals.py

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.analysis_service import prepare_latest_analysis_dataframe # noqa: E402
from services.mapping_service import get_stock_info # noqa: E402
from services.signal_service import ( # noqa: E402
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)


VALIDATION_TICKERS = ["MARK", "BBCA", "ADRO", "GOTO"]

DISPLAY_COLUMNS = [
    "Close",
    "Volume",
    "SMA10",
    "SMA50",
    "Volume_MA20",
    "MACD",
    "MACD_Signal",
    "MACD_Histogram",
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


def validate_ma_crossover(df: pd.DataFrame) -> dict[str, object]:
    if len(df) < 2:
        return {"conclusion": "PERLU_CEK_DATA_KURANG"}

    prev = df.iloc[-2]
    latest = df.iloc[-1]

    prev_date = df.index[-2].strftime("%Y-%m-%d")
    latest_date = df.index[-1].strftime("%Y-%m-%d")
    latest_signal = str(latest.get(MA_CROSSOVER_SIGNAL_COLUMN, "HOLD")).upper()

    required = ["SMA10", "SMA50", "Volume", "Volume_MA20"]

    values_available = (
        prev[["SMA10", "SMA50"]].notna().all()
        and latest[required].notna().all()
    )

    buy_valid = (
        values_available
        and prev["SMA10"] <= prev["SMA50"]
        and latest["SMA10"] > latest["SMA50"]
        and latest["Volume"] >= latest["Volume_MA20"] * 0.8
    )

    sell_valid = (
        values_available
        and prev["SMA10"] >= prev["SMA50"]
        and latest["SMA10"] < latest["SMA50"]
        and latest["Volume"] >= latest["Volume_MA20"] * 0.8
    )

    raw_buy_cross = (
        values_available
        and prev["SMA10"] <= prev["SMA50"]
        and latest["SMA10"] > latest["SMA50"]
    )

    raw_sell_cross = (
        values_available
        and prev["SMA10"] >= prev["SMA50"]
        and latest["SMA10"] < latest["SMA50"]
    )

    volume_valid = (
        pd.notna(latest.get("Volume"))
        and pd.notna(latest.get("Volume_MA20"))
        and latest["Volume"] >= latest["Volume_MA20"] * 0.8
    )

    if latest_signal == "BUY" and buy_valid:
        conclusion = "VALID_BUY_CROSSOVER_VOLUME"
    elif latest_signal == "SELL" and sell_valid:
        conclusion = "VALID_SELL_CROSSOVER_VOLUME"
    elif latest_signal == "HOLD" and not buy_valid and not sell_valid:
        conclusion = "VALID_HOLD_SYARAT_FINAL_BELUM_TERPENUHI"
    else:
        conclusion = "PERLU_CEK_LOGIKA_ATAU_DATA"

    return {
        "prev_date": prev_date,
        "latest_date": latest_date,
        "prev_sma10": prev.get("SMA10"),
        "prev_sma50": prev.get("SMA50"),
        "latest_sma10": latest.get("SMA10"),
        "latest_sma50": latest.get("SMA50"),
        "latest_volume": latest.get("Volume"),
        "latest_volume_ma20": latest.get("Volume_MA20"),
        "latest_signal": latest_signal,
        "raw_buy_cross": raw_buy_cross,
        "raw_sell_cross": raw_sell_cross,
        "volume_valid": volume_valid,
        "buy_valid": buy_valid,
        "sell_valid": sell_valid,
        "conclusion": conclusion,
    }


def validate_ticker(ticker: str) -> None:
    print("=" * 90)
    print(f"VALIDASI TICKER: {ticker}")

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

    ma = validate_ma_crossover(df)

    print("Validasi MA Crossover final dua baris terakhir:")
    print(f"Tanggal sebelumnya : {ma['prev_date']}")
    print(f"SMA10 sebelumnya   : {fmt(ma['prev_sma10'])}")
    print(f"SMA50 sebelumnya   : {fmt(ma['prev_sma50'])}")
    print(f"Tanggal terbaru    : {ma['latest_date']}")
    print(f"SMA10 terbaru      : {fmt(ma['latest_sma10'])}")
    print(f"SMA50 terbaru      : {fmt(ma['latest_sma50'])}")
    print(f"Volume terbaru     : {fmt(ma['latest_volume'])}")
    print(f"VolMA20 terbaru    : {fmt(ma['latest_volume_ma20'])}")
    print(f"Sinyal terbaru     : {ma['latest_signal']}")
    print(f"Volume valid       : {ma['volume_valid']}")
    print(f"Kesimpulan         : {ma['conclusion']}")
    print()


def main() -> None:
    for ticker in VALIDATION_TICKERS:
        validate_ticker(ticker)


if __name__ == "__main__":
    main()