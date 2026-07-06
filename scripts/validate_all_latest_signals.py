from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.analysis_service import (
    get_sector_best_indicator,
    prepare_latest_analysis_dataframe,
)
from services.mapping_service import load_mapping
from services.signal_service import (
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)


ACTIVE_SIGNALS = {"BUY", "SELL"}


def validate_ma(df: pd.DataFrame) -> str:
    if len(df) < 2:
        return "PERLU_CEK_DATA_KURANG"

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    signal = str(latest.get(MA_CROSSOVER_SIGNAL_COLUMN, "HOLD")).upper()

    required_current = ["SMA10", "SMA50", "Volume", "Volume_MA20"]
    required_previous = ["SMA10", "SMA50"]

    if prev[required_previous].isna().any() or latest[required_current].isna().any():
        return "PERLU_CEK_NILAI_MA_NAN"

    volume_confirmed = latest["Volume"] >= latest["Volume_MA20"] * 0.8

    buy_valid = (
        prev["SMA10"] <= prev["SMA50"]
        and latest["SMA10"] > latest["SMA50"]
        and volume_confirmed
    )

    sell_valid = (
        prev["SMA10"] >= prev["SMA50"]
        and latest["SMA10"] < latest["SMA50"]
        and volume_confirmed
    )

    if signal == "BUY" and buy_valid:
        return "VALID_BUY"
    if signal == "SELL" and sell_valid:
        return "VALID_SELL"
    if signal == "HOLD" and not buy_valid and not sell_valid:
        return "VALID_HOLD"

    return "PERLU_CEK"

def validate_macd(df: pd.DataFrame) -> str:
    if len(df) < 2:
        return "PERLU_CEK_DATA_KURANG"

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    signal = str(latest.get(MACD_TRADE_SIGNAL_COLUMN, "HOLD")).upper()

    required_current = ["Close", "SMA50", "MACD", "MACD_Signal", "Volume", "Volume_MA20"]
    required_previous = ["MACD", "MACD_Signal"]

    if prev[required_previous].isna().any() or latest[required_current].isna().any():
        return "PERLU_CEK_NILAI_MACD_NAN"

    if latest["Close"] == 0:
        return "PERLU_CEK_CLOSE_NOL"

    bullish_distance = (latest["MACD"] - latest["MACD_Signal"]) / latest["Close"]
    bearish_distance = (latest["MACD_Signal"] - latest["MACD"]) / latest["Close"]
    volume_confirmed = latest["Volume"] >= latest["Volume_MA20"]

    buy_valid = (
        prev["MACD"] <= prev["MACD_Signal"]
        and latest["MACD"] > latest["MACD_Signal"]
        and latest["Close"] > latest["SMA50"]
        and bullish_distance >= 0.001
        and volume_confirmed
    )

    sell_valid = (
        prev["MACD"] >= prev["MACD_Signal"]
        and latest["MACD"] < latest["MACD_Signal"]
        and latest["Close"] < latest["SMA50"]
        and bearish_distance >= 0.001
        and volume_confirmed
    )

    if signal == "BUY" and buy_valid:
        return "VALID_BUY"
    if signal == "SELL" and sell_valid:
        return "VALID_SELL"
    if signal == "HOLD" and not buy_valid and not sell_valid:
        return "VALID_HOLD"

    return "PERLU_CEK"


def validate_rsi(df: pd.DataFrame) -> str:
    if len(df) < 2:
        return "PERLU_CEK_DATA_KURANG"

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    signal = str(latest.get(RSI_SIGNAL_COLUMN, "HOLD")).upper()

    required = ["Close", "SMA50", "RSI"]
    if prev[required].isna().any() or latest[required].isna().any():
        return "PERLU_CEK_NILAI_RSI_NAN"

    buy_valid = (
        prev["RSI"] < 30
        and latest["RSI"] >= 30
        and latest["Close"] > latest["SMA50"]
    )

    sell_valid = (
        prev["RSI"] > 70
        and latest["RSI"] <= 70
        and latest["Close"] < latest["SMA50"]
    )

    if signal == "BUY" and buy_valid:
        return "VALID_BUY"
    if signal == "SELL" and sell_valid:
        return "VALID_SELL"
    if signal == "HOLD" and not buy_valid and not sell_valid:
        return "VALID_HOLD"

    return "PERLU_CEK"


def get_best_signal_column(indicator: str) -> str:
    indicator = str(indicator).strip()

    if indicator == "MA Crossover":
        return MA_CROSSOVER_SIGNAL_COLUMN
    if indicator == "MACD":
        return MACD_TRADE_SIGNAL_COLUMN
    if indicator == "RSI":
        return RSI_SIGNAL_COLUMN

    return ""


def validate_by_indicator(df: pd.DataFrame, indicator: str) -> str:
    indicator = str(indicator).strip()

    if indicator == "MA Crossover":
        return validate_ma(df)
    if indicator == "MACD":
        return validate_macd(df)
    if indicator == "RSI":
        return validate_rsi(df)

    return "PERLU_CEK_INDIKATOR_TIDAK_DIKENALI"


def main() -> None:
    mapping = load_mapping()

    sample = mapping[
        (mapping["is_sample"].astype(str).str.strip().str.casefold() == "ya")
        & (mapping["status_data"].astype(str).str.strip().str.casefold() == "lengkap")
    ].copy()

    rows: list[dict[str, object]] = []

    for _, stock in sample.iterrows():
        ticker = stock["ticker"]
        ticker_yfinance = stock["ticker_yfinance"]
        sector = stock["sektor"]

        try:
            best = get_sector_best_indicator(str(sector))
            if not best:
                rows.append(
                    {
                        "ticker": ticker,
                        "ticker_yfinance": ticker_yfinance,
                        "sector": sector,
                        "best_indicator": None,
                        "latest_date": None,
                        "latest_signal": None,
                        "validation_status": "ERROR_BEST_INDICATOR_TIDAK_TERSEDIA",
                    }
                )
                continue

            best_indicator = str(best["indicator"])
            signal_column = get_best_signal_column(best_indicator)

            df = prepare_latest_analysis_dataframe(str(ticker_yfinance))
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            latest_signal = str(latest.get(signal_column, "HOLD")).upper()
            validation_status = validate_by_indicator(df, best_indicator)

            rows.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "best_indicator": best_indicator,
                    "signal_column": signal_column,
                    "rows": len(df),
                    "start_date": df.index.min().strftime("%Y-%m-%d"),
                    "prev_date": df.index[-2].strftime("%Y-%m-%d"),
                    "latest_date": df.index[-1].strftime("%Y-%m-%d"),
                    "prev_close": prev.get("Close"),
                    "latest_close": latest.get("Close"),
                    "latest_signal": latest_signal,
                    "ma_signal": latest.get(MA_CROSSOVER_SIGNAL_COLUMN),
                    "macd_signal": latest.get(MACD_TRADE_SIGNAL_COLUMN),
                    "rsi_signal": latest.get(RSI_SIGNAL_COLUMN),
                    "sma10_prev": prev.get("SMA10"),
                    "sma50_prev": prev.get("SMA50"),
                    "sma10_latest": latest.get("SMA10"),
                    "sma50_latest": latest.get("SMA50"),
                    "volume_latest": latest.get("Volume"),
                    "volume_ma20_latest": latest.get("Volume_MA20"),
                    "macd_prev": prev.get("MACD"),
                    "macd_signal_prev": prev.get("MACD_Signal"),
                    "macd_latest": latest.get("MACD"),
                    "macd_signal_latest": latest.get("MACD_Signal"),
                    "macd_histogram_latest": latest.get("MACD_Histogram"),
                    "rsi_prev": prev.get("RSI"),
                    "rsi_latest": latest.get("RSI"),
                    "validation_status": validation_status,
                                    }
            )

        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "best_indicator": None,
                    "latest_date": None,
                    "latest_signal": None,
                    "validation_status": f"ERROR:{type(exc).__name__}:{exc}",
                }
            )

    result = pd.DataFrame(rows)

    output_path = PROJECT_ROOT / "data" / "validate_all_latest_signals.csv"
    result.to_csv(output_path, index=False)

    print("=" * 100)
    print("VALIDASI SEMUA SINYAL TERBARU BERDASARKAN INDIKATOR TERBAIK SEKTOR")
    print("=" * 100)
    print()

    display_columns = [
        "ticker",
        "sector",
        "best_indicator",
        "latest_date",
        "latest_signal",
        "validation_status",
    ]

    print(result[display_columns].to_string(index=False))
    print()

    print("=" * 100)
    print("RINGKASAN STATUS VALIDASI")
    print("=" * 100)
    print(result["validation_status"].value_counts().to_string())
    print()

    print("=" * 100)
    print("DATA PERLU CEK / ERROR")
    print("=" * 100)

    need_check = result[
        result["validation_status"].astype(str).str.contains("PERLU_CEK|ERROR", case=False, na=False)
    ]

    if need_check.empty:
        print("Tidak ada data PERLU_CEK atau ERROR.")
    else:
        print(need_check[display_columns].to_string(index=False))

    print()
    print(f"File hasil validasi disimpan ke: {output_path}")


if __name__ == "__main__":
    main()