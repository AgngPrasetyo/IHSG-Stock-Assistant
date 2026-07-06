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
from services.metric_service import evaluate_signal_performance  # noqa: E402
from services.wfa_service import generate_wfa_windows  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "data"
WINDOW_OUTPUT_PATH = OUTPUT_DIR / "audit_ma_variant_wfa_window_results.csv"
SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_ma_variant_wfa_sector_aggregate.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "audit_ma_variant_wfa_summary.csv"
BEST_BY_SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_ma_variant_wfa_best_by_sector.csv"
ERROR_OUTPUT_PATH = OUTPUT_DIR / "audit_ma_variant_wfa_errors.csv"

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"

EVALUATION_HORIZON_PERIODS = 3
IN_SAMPLE_MONTHS = 6
OUT_SAMPLE_MONTHS = 3
SHIFT_MONTHS = 3

MA_VARIANTS = [
    {
        "variant": "SMA20/SMA50",
        "fast_window": 20,
        "slow_window": 50,
        "signal_column": "MA_20_50_Signal",
    },
    {
        "variant": "SMA14/SMA21",
        "fast_window": 14,
        "slow_window": 21,
        "signal_column": "MA_14_21_Signal",
    },
    {
        "variant": "SMA10/SMA50",
        "fast_window": 10,
        "slow_window": 50,
        "signal_column": "MA_10_50_Signal",
    },
]


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


def format_date(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


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


def run_stock_variant_wfa(stock: pd.Series) -> list[dict[str, Any]]:
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

        signal_df = combined.copy()

        for variant in MA_VARIANTS:
            signal_df = generate_ma_variant_signal(
                signal_df,
                int(variant["fast_window"]),
                int(variant["slow_window"]),
                str(variant["signal_column"]),
            )

        evaluation = signal_df.loc[signal_df.index.isin(out_df.index)].copy()

        for variant in MA_VARIANTS:
            signal_column = str(variant["signal_column"])
            metric = evaluate_signal_performance(
                evaluation,
                signal_column,
                forward_periods=EVALUATION_HORIZON_PERIODS,
            )

            records.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "window_id": int(window["window_id"]),
                    "variant": variant["variant"],
                    "fast_window": int(variant["fast_window"]),
                    "slow_window": int(variant["slow_window"]),
                    "signal_column": signal_column,
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
    if window_df.empty:
        return pd.DataFrame()

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

    if active_windows.empty:
        grouped["hit_rate"] = 0.0
    else:
        hit_rate_df = (
            active_windows.groupby(group_keys, as_index=False)["hit_rate"]
            .mean()
            .reset_index(drop=True)
        )
        grouped = grouped.merge(hit_rate_df, on=group_keys, how="left")
        grouped["hit_rate"] = grouped["hit_rate"].fillna(0.0)

    return grouped


def select_best_by_sector(sector_df: pd.DataFrame) -> pd.DataFrame:
    if sector_df.empty:
        return pd.DataFrame()

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

    for _, stock in sample_df.iterrows():
        ticker = str(stock.get("ticker", "UNKNOWN"))
        try:
            records.extend(run_stock_variant_wfa(stock))
            print(f"OK  {ticker}")
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})
            print(f"ERR {ticker}: {exc}")

    window_df = pd.DataFrame(records)
    window_df.to_csv(WINDOW_OUTPUT_PATH, index=False)

    if window_df.empty:
        print("Tidak ada hasil WFA yang berhasil dibuat.")
        return

    sector_df = aggregate_results(window_df, ["sector", "variant", "fast_window", "slow_window"])
    sector_df = sector_df.sort_values(
        ["sector", "directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)
    sector_df.to_csv(SECTOR_OUTPUT_PATH, index=False)

    summary_df = aggregate_results(window_df, ["variant", "fast_window", "slow_window"])
    summary_df = summary_df.sort_values(
        ["directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    best_by_sector_df = select_best_by_sector(sector_df)
    best_by_sector_df.to_csv(BEST_BY_SECTOR_OUTPUT_PATH, index=False)

    if errors:
        pd.DataFrame(errors).to_csv(ERROR_OUTPUT_PATH, index=False)

    print("\nAudit WFA varian MA selesai.")
    print(f"Window results     : {WINDOW_OUTPUT_PATH}")
    print(f"Sector aggregate   : {SECTOR_OUTPUT_PATH}")
    print(f"Summary aggregate  : {SUMMARY_OUTPUT_PATH}")
    print(f"Best by sector     : {BEST_BY_SECTOR_OUTPUT_PATH}")

    if errors:
        print(f"Errors             : {ERROR_OUTPUT_PATH}")

    print("\nRingkasan keseluruhan:")
    print(
        summary_df[
            [
                "variant",
                "fast_window",
                "slow_window",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
            ]
        ].to_string(index=False)
    )

    print("\nVarian terbaik per sektor:")
    print(
        best_by_sector_df[
            [
                "sector",
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