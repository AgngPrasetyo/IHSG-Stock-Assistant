from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from services.data_service import REQUIRED_OHLCV_COLUMNS, load_or_fetch_price_data  # noqa: E402
from services.indicator_service import calculate_sma  # noqa: E402
from services.mapping_service import load_mapping  # noqa: E402


OUTPUT_PATH = PROJECT_ROOT / "data" / "audit_ma_variant_latest_signals.csv"

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"


def generate_ma_variant_signal(
    df: pd.DataFrame,
    fast_window: int,
    slow_window: int,
    signal_column: str,
) -> pd.DataFrame:
    """Generate BUY/SELL/HOLD signal for a custom SMA crossover variant."""
    result = df.copy()

    fast_col = f"SMA{fast_window}"
    slow_col = f"SMA{slow_window}"

    if fast_col not in result.columns:
        result[fast_col] = calculate_sma(result, fast_window)
    if slow_col not in result.columns:
        result[slow_col] = calculate_sma(result, slow_window)

    result[signal_column] = HOLD

    valid = (
        result[[fast_col, slow_col]].notna().all(axis=1)
        & result[[fast_col, slow_col]].shift(1).notna().all(axis=1)
    )

    buy = (
        valid
        & (result[fast_col].shift(1) <= result[slow_col].shift(1))
        & (result[fast_col] > result[slow_col])
    )

    sell = (
        valid
        & (result[fast_col].shift(1) >= result[slow_col].shift(1))
        & (result[fast_col] < result[slow_col])
    )

    result.loc[buy, signal_column] = BUY
    result.loc[sell, signal_column] = SELL

    return result


def fmt(value: Any) -> Any:
    """Return CSV-friendly values."""
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 4)
    return value


def latest_variant_record(stock: pd.Series) -> dict[str, Any]:
    """Build latest SMA variant comparison for one stock."""
    ticker = str(stock["ticker"])
    ticker_yfinance = str(stock["ticker_yfinance"])
    sector = str(stock["sektor"])

    price_df = load_or_fetch_price_data(ticker_yfinance, use_cache=True)
    df = price_df.dropna(subset=REQUIRED_OHLCV_COLUMNS).copy()

    if df.empty:
        raise ValueError(f"Data OHLCV kosong untuk {ticker}")

    df = generate_ma_variant_signal(df, 20, 50, "MA_20_50_Signal")
    df = generate_ma_variant_signal(df, 14, 21, "MA_14_21_Signal")
    df = generate_ma_variant_signal(df, 10, 50, "MA_10_50_Signal")

    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) >= 2 else None

    return {
        "ticker": ticker,
        "ticker_yfinance": ticker_yfinance,
        "sector": sector,
        "latest_date": pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d"),
        "previous_date": pd.Timestamp(df.index[-2]).strftime("%Y-%m-%d")
        if len(df) >= 2
        else None,
        "close": fmt(latest.get("Close")),

        # Current final system configuration: SMA20/SMA50
        "sma20_previous": fmt(previous.get("SMA20")) if previous is not None else None,
        "sma50_previous": fmt(previous.get("SMA50")) if previous is not None else None,
        "sma20_latest": fmt(latest.get("SMA20")),
        "sma50_latest": fmt(latest.get("SMA50")),
        "signal_20_50": latest.get("MA_20_50_Signal"),

        # Experimental variant: SMA14/SMA21
        "sma14_previous": fmt(previous.get("SMA14")) if previous is not None else None,
        "sma21_previous": fmt(previous.get("SMA21")) if previous is not None else None,
        "sma14_latest": fmt(latest.get("SMA14")),
        "sma21_latest": fmt(latest.get("SMA21")),
        "signal_14_21": latest.get("MA_14_21_Signal"),

        # Experimental variant: SMA10/SMA50
        "sma10_previous": fmt(previous.get("SMA10")) if previous is not None else None,
        "sma10_latest": fmt(latest.get("SMA10")),
        "signal_10_50": latest.get("MA_10_50_Signal"),
    }


def main() -> None:
    mapping_df = load_mapping()

    sample_df = mapping_df[
        mapping_df["is_sample"].astype(str).str.strip().str.casefold().eq("ya")
        & mapping_df["status_data"].astype(str).str.strip().str.casefold().eq("lengkap")
    ].copy()

    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for _, stock in sample_df.iterrows():
        ticker = str(stock.get("ticker", "UNKNOWN"))
        try:
            records.append(latest_variant_record(stock))
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})

    result_df = pd.DataFrame(records)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT_PATH, index=False)

    print(f"Audit selesai: {OUTPUT_PATH}")
    print(f"Jumlah saham berhasil diaudit: {len(result_df)}")

    if not result_df.empty:
        print("\nRingkasan sinyal terbaru:")

        print("\nSMA20/SMA50")
        print(result_df["signal_20_50"].value_counts(dropna=False).to_string())

        print("\nSMA14/SMA21")
        print(result_df["signal_14_21"].value_counts(dropna=False).to_string())

        print("\nSMA10/SMA50")
        print(result_df["signal_10_50"].value_counts(dropna=False).to_string())

        changed_14_21 = result_df[
            result_df["signal_14_21"] != result_df["signal_20_50"]
        ]

        changed_10_50 = result_df[
            result_df["signal_10_50"] != result_df["signal_20_50"]
        ]

        print("\nBerbeda dari SMA20/SMA50:")
        print(f"SMA14/SMA21: {len(changed_14_21)} saham")
        print(f"SMA10/SMA50: {len(changed_10_50)} saham")

        if len(changed_14_21):
            print("\nTicker berbeda pada SMA14/SMA21:")
            print(
                changed_14_21[
                    ["ticker", "sector", "signal_20_50", "signal_14_21"]
                ].to_string(index=False)
            )

        if len(changed_10_50):
            print("\nTicker berbeda pada SMA10/SMA50:")
            print(
                changed_10_50[
                    ["ticker", "sector", "signal_20_50", "signal_10_50"]
                ].to_string(index=False)
            )

    if errors:
        error_path = OUTPUT_PATH.with_name("audit_ma_variant_latest_errors.csv")
        pd.DataFrame(errors).to_csv(error_path, index=False)

        print(f"\nAda error pada {len(errors)} saham.")
        print(f"Detail error: {error_path}")


if __name__ == "__main__":
    main()