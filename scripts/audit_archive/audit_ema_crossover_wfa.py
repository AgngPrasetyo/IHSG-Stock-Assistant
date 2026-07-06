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

WINDOW_OUTPUT_PATH = OUTPUT_DIR / "audit_ema_crossover_wfa_window_results.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "audit_ema_crossover_wfa_summary.csv"
SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_ema_crossover_wfa_sector_aggregate.csv"
BEST_OVERALL_OUTPUT_PATH = OUTPUT_DIR / "audit_ema_crossover_wfa_best_overall.csv"
BEST_BY_SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_ema_crossover_wfa_best_by_sector.csv"
ERROR_OUTPUT_PATH = OUTPUT_DIR / "audit_ema_crossover_wfa_errors.csv"

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"

EVALUATION_HORIZON_PERIODS = 3
IN_SAMPLE_MONTHS = 6
OUT_SAMPLE_MONTHS = 3
SHIFT_MONTHS = 3

MIN_ACTIVE_SIGNALS_OVERALL = 30
MIN_ACTIVE_SIGNALS_SECTOR = 10


VARIANT_CONFIGS = [
    {
        "variant": "SMA20/SMA50 + Threshold 0.10% + Volume >= VolMA20",
        "ma_type": "SMA",
        "fast_window": 20,
        "slow_window": 50,
        "threshold_pct": 0.001,
        "use_volume_filter": True,
        "volume_window": 20,
        "volume_multiplier": 1.0,
        "signal_column": "SMA_20_50_TH_0p001_VOL_Signal",
    },
    {
        "variant": "EMA10/EMA50 | No Threshold | No Volume Filter",
        "ma_type": "EMA",
        "fast_window": 10,
        "slow_window": 50,
        "threshold_pct": 0.0,
        "use_volume_filter": False,
        "volume_window": 20,
        "volume_multiplier": 0.0,
        "signal_column": "EMA_10_50_TH_0p0_NOVOL_Signal",
    },
    {
        "variant": "EMA10/EMA50 | Threshold 0.10% | Volume >= VolMA20",
        "ma_type": "EMA",
        "fast_window": 10,
        "slow_window": 50,
        "threshold_pct": 0.001,
        "use_volume_filter": True,
        "volume_window": 20,
        "volume_multiplier": 1.0,
        "signal_column": "EMA_10_50_TH_0p001_VOL_Signal",
    },
    {
        "variant": "EMA14/EMA21 | No Threshold | No Volume Filter",
        "ma_type": "EMA",
        "fast_window": 14,
        "slow_window": 21,
        "threshold_pct": 0.0,
        "use_volume_filter": False,
        "volume_window": 20,
        "volume_multiplier": 0.0,
        "signal_column": "EMA_14_21_TH_0p0_NOVOL_Signal",
    },
    {
        "variant": "EMA14/EMA21 | Threshold 0.10% | Volume >= VolMA20",
        "ma_type": "EMA",
        "fast_window": 14,
        "slow_window": 21,
        "threshold_pct": 0.001,
        "use_volume_filter": True,
        "volume_window": 20,
        "volume_multiplier": 1.0,
        "signal_column": "EMA_14_21_TH_0p001_VOL_Signal",
    },
]


def calculate_ema(df: pd.DataFrame, window: int) -> pd.Series:
    return df["Close"].ewm(span=window, adjust=False).mean()


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


def ensure_ma_columns(
    df: pd.DataFrame,
    ma_type: str,
    fast_window: int,
    slow_window: int,
) -> pd.DataFrame:
    result = df.copy()

    fast_col = f"{ma_type}{fast_window}"
    slow_col = f"{ma_type}{slow_window}"

    if fast_col not in result.columns:
        if ma_type == "SMA":
            result[fast_col] = calculate_sma(result, fast_window)
        elif ma_type == "EMA":
            result[fast_col] = calculate_ema(result, fast_window)
        else:
            raise ValueError(f"Jenis moving average tidak dikenal: {ma_type}")

    if slow_col not in result.columns:
        if ma_type == "SMA":
            result[slow_col] = calculate_sma(result, slow_window)
        elif ma_type == "EMA":
            result[slow_col] = calculate_ema(result, slow_window)
        else:
            raise ValueError(f"Jenis moving average tidak dikenal: {ma_type}")

    return result


def ensure_volume_ma(df: pd.DataFrame, volume_window: int = 20) -> pd.DataFrame:
    result = df.copy()
    volume_ma_col = f"Volume_MA{volume_window}"

    if "Volume" not in result.columns:
        raise ValueError("Kolom Volume tidak tersedia.")

    if volume_ma_col not in result.columns:
        result[volume_ma_col] = result["Volume"].rolling(window=volume_window).mean()

    return result


def generate_crossover_signal(
    df: pd.DataFrame,
    ma_type: str,
    fast_window: int,
    slow_window: int,
    signal_column: str,
    threshold_pct: float = 0.0,
    use_volume_filter: bool = False,
    volume_window: int = 20,
    volume_multiplier: float = 1.0,
) -> pd.DataFrame:
    result = ensure_ma_columns(df, ma_type, fast_window, slow_window)

    if use_volume_filter:
        result = ensure_volume_ma(result, volume_window)

    fast_col = f"{ma_type}{fast_window}"
    slow_col = f"{ma_type}{slow_window}"
    volume_ma_col = f"Volume_MA{volume_window}"

    result[signal_column] = HOLD

    required_columns = [fast_col, slow_col, "Close"]
    if use_volume_filter:
        required_columns.extend(["Volume", volume_ma_col])

    valid = (
        result[required_columns].notna().all(axis=1)
        & result[[fast_col, slow_col]].shift(1).notna().all(axis=1)
    )

    bullish_cross = (
        valid
        & (result[fast_col].shift(1) <= result[slow_col].shift(1))
        & (result[fast_col] > result[slow_col])
    )

    bearish_cross = (
        valid
        & (result[fast_col].shift(1) >= result[slow_col].shift(1))
        & (result[fast_col] < result[slow_col])
    )

    if threshold_pct > 0:
        bullish_distance = (result[fast_col] - result[slow_col]) / result["Close"]
        bearish_distance = (result[slow_col] - result[fast_col]) / result["Close"]

        bullish_cross = bullish_cross & (bullish_distance >= threshold_pct)
        bearish_cross = bearish_cross & (bearish_distance >= threshold_pct)

    if use_volume_filter:
        volume_confirmed = result["Volume"] >= result[volume_ma_col] * volume_multiplier
        bullish_cross = bullish_cross & volume_confirmed
        bearish_cross = bearish_cross & volume_confirmed

    result.loc[bullish_cross, signal_column] = BUY
    result.loc[bearish_cross, signal_column] = SELL

    return result


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

        signal_df = combined.copy()

        for variant in VARIANT_CONFIGS:
            signal_df = generate_crossover_signal(
                signal_df,
                ma_type=str(variant["ma_type"]),
                fast_window=int(variant["fast_window"]),
                slow_window=int(variant["slow_window"]),
                signal_column=str(variant["signal_column"]),
                threshold_pct=float(variant["threshold_pct"]),
                use_volume_filter=bool(variant["use_volume_filter"]),
                volume_window=int(variant["volume_window"]),
                volume_multiplier=float(variant["volume_multiplier"]),
            )

        evaluation = signal_df.loc[signal_df.index.isin(out_df.index)].copy()

        for variant in VARIANT_CONFIGS:
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
                    "ma_type": variant["ma_type"],
                    "fast_window": int(variant["fast_window"]),
                    "slow_window": int(variant["slow_window"]),
                    "threshold_pct": float(variant["threshold_pct"]),
                    "use_volume_filter": bool(variant["use_volume_filter"]),
                    "volume_window": int(variant["volume_window"]),
                    "volume_multiplier": float(variant["volume_multiplier"]),
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


def add_reliability_flag(df: pd.DataFrame, min_active_signals: int) -> pd.DataFrame:
    result = df.copy()
    result["meets_min_active_signals"] = result["total_active_signals"] >= min_active_signals
    return result


def select_best_overall(summary_df: pd.DataFrame) -> pd.DataFrame:
    reliable = summary_df[
        summary_df["total_active_signals"] >= MIN_ACTIVE_SIGNALS_OVERALL
    ].copy()

    if reliable.empty:
        reliable = summary_df.copy()

    return reliable.sort_values(
        ["directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def select_best_by_sector(sector_df: pd.DataFrame) -> pd.DataFrame:
    reliable = sector_df[
        sector_df["total_active_signals"] >= MIN_ACTIVE_SIGNALS_SECTOR
    ].copy()

    if reliable.empty:
        reliable = sector_df.copy()

    sorted_df = reliable.sort_values(
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
    print(f"Jumlah varian crossover yang diuji: {len(VARIANT_CONFIGS)}")
    print("Mulai menjalankan audit EMA Crossover...\n")

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

    group_keys = [
        "variant",
        "ma_type",
        "fast_window",
        "slow_window",
        "threshold_pct",
        "use_volume_filter",
        "volume_window",
        "volume_multiplier",
        "signal_column",
    ]

    summary_df = aggregate_results(window_df, group_keys)
    summary_df = add_reliability_flag(summary_df, MIN_ACTIVE_SIGNALS_OVERALL)
    summary_df = select_best_overall(summary_df)
    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    sector_group_keys = ["sector", *group_keys]
    sector_df = aggregate_results(window_df, sector_group_keys)
    sector_df = add_reliability_flag(sector_df, MIN_ACTIVE_SIGNALS_SECTOR)
    sector_df = sector_df.sort_values(
        ["sector", "directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[True, False, False, False],
    ).reset_index(drop=True)
    sector_df.to_csv(SECTOR_OUTPUT_PATH, index=False)

    best_overall_df = summary_df.copy()
    best_overall_df.to_csv(BEST_OVERALL_OUTPUT_PATH, index=False)

    best_by_sector_df = select_best_by_sector(sector_df)
    best_by_sector_df.to_csv(BEST_BY_SECTOR_OUTPUT_PATH, index=False)

    if errors:
        pd.DataFrame(errors).to_csv(ERROR_OUTPUT_PATH, index=False)

    print("\nAudit EMA Crossover selesai.")
    print(f"Window results       : {WINDOW_OUTPUT_PATH}")
    print(f"Summary aggregate    : {SUMMARY_OUTPUT_PATH}")
    print(f"Sector aggregate     : {SECTOR_OUTPUT_PATH}")
    print(f"Best overall         : {BEST_OVERALL_OUTPUT_PATH}")
    print(f"Best by sector       : {BEST_BY_SECTOR_OUTPUT_PATH}")

    if errors:
        print(f"Errors               : {ERROR_OUTPUT_PATH}")

    print("\nRingkasan keseluruhan:")
    print(
        best_overall_df[
            [
                "variant",
                "ma_type",
                "fast_window",
                "slow_window",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
                "meets_min_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nVarian terbaik per sektor:")
    print(
        best_by_sector_df[
            [
                "sector",
                "variant",
                "ma_type",
                "fast_window",
                "slow_window",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
                "meets_min_active_signals",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()