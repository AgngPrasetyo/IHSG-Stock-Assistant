# scripts/validate_latest_signals.py

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.analysis_service import (  # noqa: E402
    get_sector_best_indicator,
    prepare_latest_analysis_dataframe,
)
from services.mapping_service import get_stock_info  # noqa: E402
from services.signal_service import (  # noqa: E402
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)


DEFAULT_TICKERS = ["MARK", "BBCA", "ADRO", "GOTO"]


def _safe_signal(value: object) -> str:
    signal = str(value).strip().upper()
    return signal if signal in {"BUY", "SELL", "HOLD"} else "HOLD"


def _build_result(
    indicator: str,
    signal_column: str,
    actual_signal: str,
    expected_signal: str,
    condition: str,
    status_prefix: str,
) -> dict[str, object]:
    status = (
        f"VALID_{actual_signal}"
        if actual_signal == expected_signal
        else f"ERROR_SIGNAL_MISMATCH_EXPECTED_{expected_signal}_ACTUAL_{actual_signal}"
    )

    return {
        "indicator": indicator,
        "signal_column": signal_column,
        "actual_signal": actual_signal,
        "expected_signal": expected_signal,
        "condition": condition,
        "validation_status": status if status_prefix == "OK" else status_prefix,
    }


def validate_ma_crossover(df: pd.DataFrame) -> dict[str, object]:
    indicator = "MA Crossover"
    signal_column = MA_CROSSOVER_SIGNAL_COLUMN

    if len(df) < 2:
        return _build_result(indicator, signal_column, "HOLD", "HOLD", "Data kurang dari 2 baris.", "ERROR_DATA_KURANG")

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    actual_signal = _safe_signal(latest.get(signal_column, "HOLD"))

    required_previous = ["SMA10", "SMA50"]
    required_latest = ["SMA10", "SMA50"]

    if prev[required_previous].isna().any() or latest[required_latest].isna().any():
        return _build_result(indicator, signal_column, actual_signal, "HOLD", "Nilai SMA10/SMA50 belum lengkap.", "ERROR_NILAI_MA_NAN")

    buy_condition = prev["SMA10"] <= prev["SMA50"] and latest["SMA10"] > latest["SMA50"]
    sell_condition = prev["SMA10"] >= prev["SMA50"] and latest["SMA10"] < latest["SMA50"]

    if buy_condition:
        expected_signal = "BUY"
        condition = "SMA10 memotong ke atas SMA50 pada data terakhir."
    elif sell_condition:
        expected_signal = "SELL"
        condition = "SMA10 memotong ke bawah SMA50 pada data terakhir."
    elif latest["SMA10"] > latest["SMA50"]:
        expected_signal = "HOLD"
        condition = "SMA10 > SMA50, tetapi tidak terjadi crossover baru pada data terakhir."
    elif latest["SMA10"] < latest["SMA50"]:
        expected_signal = "HOLD"
        condition = "SMA10 < SMA50, tetapi tidak terjadi crossover baru pada data terakhir."
    else:
        expected_signal = "HOLD"
        condition = "SMA10 sama dengan SMA50 pada data terakhir."

    return _build_result(indicator, signal_column, actual_signal, expected_signal, condition, "OK")


def validate_macd(df: pd.DataFrame) -> dict[str, object]:
    indicator = "MACD"
    signal_column = MACD_TRADE_SIGNAL_COLUMN

    if len(df) < 2:
        return _build_result(indicator, signal_column, "HOLD", "HOLD", "Data kurang dari 2 baris.", "ERROR_DATA_KURANG")

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    actual_signal = _safe_signal(latest.get(signal_column, "HOLD"))

    required = ["MACD", "MACD_Signal"]

    if prev[required].isna().any() or latest[required].isna().any():
        return _build_result(indicator, signal_column, actual_signal, "HOLD", "Nilai MACD/MACD Signal belum lengkap.", "ERROR_NILAI_MACD_NAN")

    buy_condition = prev["MACD"] <= prev["MACD_Signal"] and latest["MACD"] > latest["MACD_Signal"]
    sell_condition = prev["MACD"] >= prev["MACD_Signal"] and latest["MACD"] < latest["MACD_Signal"]

    if buy_condition:
        expected_signal = "BUY"
        condition = "MACD Line memotong ke atas Signal Line pada data terakhir."
    elif sell_condition:
        expected_signal = "SELL"
        condition = "MACD Line memotong ke bawah Signal Line pada data terakhir."
    elif latest["MACD"] > latest["MACD_Signal"]:
        expected_signal = "HOLD"
        condition = "MACD Line > Signal Line, tetapi tidak terjadi crossover baru pada data terakhir."
    elif latest["MACD"] < latest["MACD_Signal"]:
        expected_signal = "HOLD"
        condition = "MACD Line < Signal Line, tetapi tidak terjadi crossover baru pada data terakhir."
    else:
        expected_signal = "HOLD"
        condition = "MACD Line sama dengan Signal Line pada data terakhir."

    return _build_result(indicator, signal_column, actual_signal, expected_signal, condition, "OK")


def validate_rsi(df: pd.DataFrame) -> dict[str, object]:
    indicator = "RSI"
    signal_column = RSI_SIGNAL_COLUMN

    if len(df) < 2:
        return _build_result(indicator, signal_column, "HOLD", "HOLD", "Data kurang dari 2 baris.", "ERROR_DATA_KURANG")

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    actual_signal = _safe_signal(latest.get(signal_column, "HOLD"))

    required = ["RSI"]

    if prev[required].isna().any() or latest[required].isna().any():
        return _build_result(indicator, signal_column, actual_signal, "HOLD", "Nilai RSI belum lengkap.", "ERROR_NILAI_RSI_NAN")

    buy_condition = prev["RSI"] < 30 and latest["RSI"] >= 30
    sell_condition = prev["RSI"] > 70 and latest["RSI"] <= 70

    if buy_condition:
        expected_signal = "BUY"
        condition = "RSI keluar dari area oversold, dari bawah 30 ke 30 atau lebih."
    elif sell_condition:
        expected_signal = "SELL"
        condition = "RSI keluar dari area overbought, dari atas 70 ke 70 atau kurang."
    elif latest["RSI"] < 30:
        expected_signal = "HOLD"
        condition = "RSI masih berada di area oversold, belum keluar dari bawah 30."
    elif latest["RSI"] > 70:
        expected_signal = "HOLD"
        condition = "RSI masih berada di area overbought, belum keluar dari atas 70."
    else:
        expected_signal = "HOLD"
        condition = "RSI berada di area netral atau tidak membentuk sinyal keluar area ekstrem."

    return _build_result(indicator, signal_column, actual_signal, expected_signal, condition, "OK")


def validate_by_indicator(df: pd.DataFrame, indicator: str) -> dict[str, object]:
    indicator = str(indicator).strip()

    if indicator == "MA Crossover":
        return validate_ma_crossover(df)
    if indicator == "MACD":
        return validate_macd(df)
    if indicator == "RSI":
        return validate_rsi(df)

    return {
        "indicator": indicator,
        "signal_column": "",
        "actual_signal": None,
        "expected_signal": None,
        "condition": "Indikator tidak dikenali.",
        "validation_status": "ERROR_INDIKATOR_TIDAK_DIKENALI",
    }


def validate_ticker(ticker: str) -> dict[str, object]:
    stock_info = get_stock_info(ticker)
    if not stock_info:
        return {
            "ticker": ticker,
            "ticker_yfinance": None,
            "sector": None,
            "best_indicator": None,
            "latest_date": None,
            "validation_status": "ERROR_MAPPING_SAHAM_TIDAK_DITEMUKAN",
        }

    ticker_yfinance = str(stock_info["ticker_yfinance"])
    sector = str(stock_info["sektor"])
    best = get_sector_best_indicator(sector)

    if not best:
        return {
            "ticker": ticker,
            "ticker_yfinance": ticker_yfinance,
            "sector": sector,
            "best_indicator": None,
            "latest_date": None,
            "validation_status": "ERROR_BEST_INDICATOR_TIDAK_TERSEDIA",
        }

    best_indicator = str(best["indicator"])
    df = prepare_latest_analysis_dataframe(ticker_yfinance)

    prev = df.iloc[-2]
    latest = df.iloc[-1]
    validation = validate_by_indicator(df, best_indicator)

    result = {
        "ticker": ticker,
        "ticker_yfinance": ticker_yfinance,
        "sector": sector,
        "best_indicator": best_indicator,
        "rows": len(df),
        "start_date": df.index.min().strftime("%Y-%m-%d"),
        "prev_date": df.index[-2].strftime("%Y-%m-%d"),
        "latest_date": df.index[-1].strftime("%Y-%m-%d"),
        "prev_close": prev.get("Close"),
        "latest_close": latest.get("Close"),
        "ma_signal": latest.get(MA_CROSSOVER_SIGNAL_COLUMN),
        "macd_signal": latest.get(MACD_TRADE_SIGNAL_COLUMN),
        "rsi_signal": latest.get(RSI_SIGNAL_COLUMN),
        "sma10_prev": prev.get("SMA10"),
        "sma50_prev": prev.get("SMA50"),
        "sma10_latest": latest.get("SMA10"),
        "sma50_latest": latest.get("SMA50"),
        "macd_prev": prev.get("MACD"),
        "macd_signal_prev": prev.get("MACD_Signal"),
        "macd_latest": latest.get("MACD"),
        "macd_signal_latest": latest.get("MACD_Signal"),
        "rsi_prev": prev.get("RSI"),
        "rsi_latest": latest.get("RSI"),
    }
    result.update(validation)
    result["latest_signal"] = validation.get("actual_signal")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate latest signals for selected tickers.")
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Ticker saham yang ingin divalidasi. Jika kosong, digunakan daftar default.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers = args.tickers or DEFAULT_TICKERS

    rows = []
    for ticker in tickers:
        try:
            rows.append(validate_ticker(ticker))
        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "validation_status": f"ERROR:{type(exc).__name__}:{exc}",
                }
            )

    result = pd.DataFrame(rows)

    output_path = PROJECT_ROOT / "data" / "validate_latest_signals.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    print("=" * 100)
    print("VALIDASI SINYAL TERBARU BERDASARKAN ATURAN SISTEM SAAT INI")
    print("=" * 100)
    print()

    display_columns = [
        "ticker",
        "sector",
        "best_indicator",
        "latest_date",
        "latest_signal",
        "expected_signal",
        "validation_status",
        "condition",
    ]
    existing_display_columns = [column for column in display_columns if column in result.columns]

    print(result[existing_display_columns].to_string(index=False))
    print()
    print(f"File hasil validasi disimpan ke: {output_path}")


if __name__ == "__main__":
    main()
