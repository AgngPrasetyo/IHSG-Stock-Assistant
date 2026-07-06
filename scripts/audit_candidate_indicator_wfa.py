from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from services.data_service import REQUIRED_OHLCV_COLUMNS, load_or_fetch_price_data  # noqa: E402
from services.indicator_service import calculate_macd, calculate_rsi, calculate_sma  # noqa: E402
from services.mapping_service import load_mapping  # noqa: E402
from services.metric_service import evaluate_signal_performance  # noqa: E402
from services.wfa_service import generate_wfa_windows  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "data"
WINDOW_OUTPUT_PATH = OUTPUT_DIR / "audit_candidate_indicator_wfa_window_results.csv"
SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_candidate_indicator_wfa_sector_aggregate.csv"
BEST_BY_SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_candidate_indicator_wfa_best_by_sector.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "audit_candidate_indicator_wfa_summary.csv"
ERROR_OUTPUT_PATH = OUTPUT_DIR / "audit_candidate_indicator_wfa_errors.csv"

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"

EVALUATION_HORIZON_PERIODS = 3
IN_SAMPLE_MONTHS = 6
OUT_SAMPLE_MONTHS = 3
SHIFT_MONTHS = 3


def prepare_price_df(ticker_yfinance: str) -> pd.DataFrame:
    price_df = load_or_fetch_price_data(ticker_yfinance, use_cache=True)
    df = price_df.dropna(subset=REQUIRED_OHLCV_COLUMNS).copy()

    if df.empty:
        raise ValueError("Data OHLCV lengkap tidak tersedia.")

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.set_index("Date")

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")

    df = df[df.index.notna()].sort_index()
    df.index.name = "Date"

    return df


def ensure_base_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    if "SMA20" not in result.columns:
        result["SMA20"] = calculate_sma(result, 20)

    if "SMA50" not in result.columns:
        result["SMA50"] = calculate_sma(result, 50)

    if not {"MACD", "MACD_Signal"}.issubset(result.columns):
        result = calculate_macd(result)

    if "RSI" not in result.columns:
        result = calculate_rsi(result, 14)

    if "Volume_MA20" not in result.columns:
        result["Volume_MA20"] = result["Volume"].rolling(window=20).mean()

    return result


def generate_ma_candidate_signal(df: pd.DataFrame) -> pd.DataFrame:
    result = ensure_base_indicators(df)
    signal_column = "MA_Candidate_Signal"
    result[signal_column] = HOLD

    valid = (
        result[["SMA20", "SMA50", "Close", "Volume", "Volume_MA20"]].notna().all(axis=1)
        & result[["SMA20", "SMA50"]].shift(1).notna().all(axis=1)
    )

    bullish_cross = (
        valid
        & (result["SMA20"].shift(1) <= result["SMA50"].shift(1))
        & (result["SMA20"] > result["SMA50"])
    )

    bearish_cross = (
        valid
        & (result["SMA20"].shift(1) >= result["SMA50"].shift(1))
        & (result["SMA20"] < result["SMA50"])
    )

    bullish_distance = (result["SMA20"] - result["SMA50"]) / result["Close"]
    bearish_distance = (result["SMA50"] - result["SMA20"]) / result["Close"]

    volume_confirmed = result["Volume"] >= result["Volume_MA20"]

    bullish_cross = bullish_cross & (bullish_distance >= 0.001) & volume_confirmed
    bearish_cross = bearish_cross & (bearish_distance >= 0.001) & volume_confirmed

    result.loc[bullish_cross, signal_column] = BUY
    result.loc[bearish_cross, signal_column] = SELL

    return result


def generate_macd_candidate_signal(df: pd.DataFrame) -> pd.DataFrame:
    result = ensure_base_indicators(df)
    signal_column = "MACD_Candidate_Signal"
    result[signal_column] = HOLD

    valid = (
        result[["Close", "SMA50", "MACD", "MACD_Signal", "Volume", "Volume_MA20"]]
        .notna()
        .all(axis=1)
        & result[["MACD", "MACD_Signal"]].shift(1).notna().all(axis=1)
    )

    bullish_cross = (
        valid
        & (result["MACD"].shift(1) <= result["MACD_Signal"].shift(1))
        & (result["MACD"] > result["MACD_Signal"])
        & (result["Close"] > result["SMA50"])
    )

    bearish_cross = (
        valid
        & (result["MACD"].shift(1) >= result["MACD_Signal"].shift(1))
        & (result["MACD"] < result["MACD_Signal"])
        & (result["Close"] < result["SMA50"])
    )

    bullish_distance = (result["MACD"] - result["MACD_Signal"]) / result["Close"]
    bearish_distance = (result["MACD_Signal"] - result["MACD"]) / result["Close"]

    volume_confirmed = result["Volume"] >= result["Volume_MA20"]

    bullish_cross = bullish_cross & (bullish_distance >= 0.001) & volume_confirmed
    bearish_cross = bearish_cross & (bearish_distance >= 0.001) & volume_confirmed

    result.loc[bullish_cross, signal_column] = BUY
    result.loc[bearish_cross, signal_column] = SELL

    return result


def generate_rsi_candidate_signal(df: pd.DataFrame) -> pd.DataFrame:
    result = ensure_base_indicators(df)
    signal_column = "RSI_Candidate_Signal"
    result[signal_column] = HOLD

    valid = (
        result[["Close", "SMA50", "RSI"]].notna().all(axis=1)
        & result[["RSI"]].shift(1).notna().all(axis=1)
    )

    buy_signal = (
        valid
        & (result["RSI"].shift(1) < 30)
        & (result["RSI"] >= 30)
        & (result["Close"] > result["SMA50"])
    )

    sell_signal = (
        valid
        & (result["RSI"].shift(1) > 70)
        & (result["RSI"] <= 70)
        & (result["Close"] < result["SMA50"])
    )

    result.loc[buy_signal, signal_column] = BUY
    result.loc[sell_signal, signal_column] = SELL

    return result


INDICATOR_CONFIGS = [
    {
        "indicator": "MA Crossover",
        "variant": "SMA20/SMA50 + Threshold 0.10% + Volume >= VolMA20",
        "signal_column": "MA_Candidate_Signal",
    },
    {
        "indicator": "MACD",
        "variant": "MACD 12/26/9 + SMA50 + Histogram Threshold 0.10% + Volume >= VolMA20",
        "signal_column": "MACD_Candidate_Signal",
    },
    {
        "indicator": "RSI",
        "variant": "RSI14 30/70 + SMA50",
        "signal_column": "RSI_Candidate_Signal",
    },
]


def format_date(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def run_stock_wfa(stock: pd.Series) -> list[dict[str, Any]]:
    ticker = str(stock["ticker"])
    ticker_yfinance = str(stock["ticker_yfinance"])
    sector = str(stock["sektor"])

    df = prepare_price_df(ticker_yfinance)

    windows = generate_wfa_windows(
        df,
        in_sample_months=IN_SAMPLE_MONTHS,
        out_sample_months=OUT_SAMPLE_MONTHS,
        shift_months=SHIFT_MONTHS,
    )

    records: list[dict[str, Any]] = []

    for window in windows:
        combined = window.get("combined_df")
        out_df = window.get("out_sample_df")

        if not isinstance(combined, pd.DataFrame) or combined.empty:
            continue

        if not isinstance(out_df, pd.DataFrame) or out_df.empty:
            continue

        signal_df = ensure_base_indicators(combined.copy())
        signal_df = generate_ma_candidate_signal(signal_df)
        signal_df = generate_macd_candidate_signal(signal_df)
        signal_df = generate_rsi_candidate_signal(signal_df)

        evaluation = signal_df.loc[signal_df.index.isin(out_df.index)].copy()

        for config in INDICATOR_CONFIGS:
            metric = evaluate_signal_performance(
                evaluation,
                str(config["signal_column"]),
                forward_periods=EVALUATION_HORIZON_PERIODS,
            )

            records.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "window_id": int(window["window_id"]),
                    "indicator": config["indicator"],
                    "variant": config["variant"],
                    "signal_column": config["signal_column"],
                    "in_sample_start": format_date(window["in_sample_start"]),
                    "in_sample_end": format_date(window["in_sample_end"]),
                    "out_sample_start": format_date(window["out_sample_start"]),
                    "out_sample_end": format_date(window["out_sample_end"]),
                    "total_active_signals": int(metric["total_active_signals"]),
                    "correct_signals": int(metric["correct_signals"]),
                    "directional_accuracy": float(metric["directional_accuracy"]),
                    "hit_rate": float(metric["hit_rate"]),
                }
            )

    return records


def aggregate_results(window_df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    grouped = (
        window_df.groupby(group_keys, as_index=False)[
            ["total_active_signals", "correct_signals"]
        ]
        .sum()
        .reset_index(drop=True)
    )

    grouped["directional_accuracy"] = grouped.apply(
        lambda row: (
            int(row["correct_signals"]) / int(row["total_active_signals"]) * 100
            if int(row["total_active_signals"]) > 0
            else 0.0
        ),
        axis=1,
    )

    active_windows = window_df[window_df["total_active_signals"] > 0].copy()

    hit_rate_df = (
        active_windows.groupby(group_keys, as_index=False)["hit_rate"]
        .mean()
        .reset_index(drop=True)
    )

    grouped = grouped.merge(hit_rate_df, on=group_keys, how="left")
    grouped["hit_rate"] = grouped["hit_rate"].fillna(0.0)

    return grouped


def select_best_by_sector(sector_df: pd.DataFrame) -> pd.DataFrame:
    sorted_df = sector_df.sort_values(
        ["sector", "directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[True, False, False, False],
    )

    return sorted_df.groupby("sector", as_index=False).head(1).reset_index(drop=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    mapping_df = load_mapping()

    sample_df = mapping_df[
        mapping_df["is_sample"].astype(str).str.strip().str.casefold().eq("ya")
        & mapping_df["status_data"].astype(str).str.strip().str.casefold().eq("lengkap")
    ].copy()

    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    print(f"Jumlah saham sampel: {len(sample_df)}")
    print("Mulai menjalankan audit kandidat indikator...\n")

    for _, stock in sample_df.iterrows():
        ticker = str(stock.get("ticker", "UNKNOWN"))

        try:
            records.extend(run_stock_wfa(stock))
            print(f"OK  {ticker}")
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})
            print(f"ERR {ticker}: {exc}")

    window_df = pd.DataFrame(records)
    window_df.to_csv(WINDOW_OUTPUT_PATH, index=False)

    if window_df.empty:
        print("\nTidak ada hasil WFA yang berhasil dibuat.")
        return

    summary_df = aggregate_results(window_df, ["indicator", "variant", "signal_column"])
    summary_df = summary_df.sort_values(
        ["directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    sector_df = aggregate_results(
        window_df,
        ["sector", "indicator", "variant", "signal_column"],
    )
    sector_df = sector_df.sort_values(
        ["sector", "directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)
    sector_df.to_csv(SECTOR_OUTPUT_PATH, index=False)

    best_by_sector_df = select_best_by_sector(sector_df)
    best_by_sector_df.to_csv(BEST_BY_SECTOR_OUTPUT_PATH, index=False)

    if errors:
        pd.DataFrame(errors).to_csv(ERROR_OUTPUT_PATH, index=False)

    print("\nAudit kandidat indikator selesai.")
    print(f"Window results     : {WINDOW_OUTPUT_PATH}")
    print(f"Summary aggregate  : {SUMMARY_OUTPUT_PATH}")
    print(f"Sector aggregate   : {SECTOR_OUTPUT_PATH}")
    print(f"Best by sector     : {BEST_BY_SECTOR_OUTPUT_PATH}")

    if errors:
        print(f"Errors             : {ERROR_OUTPUT_PATH}")

    print("\nRingkasan keseluruhan kandidat indikator:")
    print(
        summary_df[
            [
                "indicator",
                "variant",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
            ]
        ].to_string(index=False)
    )

    print("\nPerbandingan indikator per sektor:")
    print(
        sector_df[
            [
                "sector",
                "indicator",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
            ]
        ].to_string(index=False)
    )

    print("\nIndikator terbaik per sektor:")
    print(
        best_by_sector_df[
            [
                "sector",
                "indicator",
                "variant",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()