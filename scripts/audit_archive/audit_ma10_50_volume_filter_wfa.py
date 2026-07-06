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

WINDOW_OUTPUT_PATH = OUTPUT_DIR / "audit_ma10_50_volume_filter_wfa_window_results.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "audit_ma10_50_volume_filter_wfa_summary.csv"
SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_ma10_50_volume_filter_wfa_sector_aggregate.csv"
BEST_BY_SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_ma10_50_volume_filter_wfa_best_by_sector.csv"
ERROR_OUTPUT_PATH = OUTPUT_DIR / "audit_ma10_50_volume_filter_wfa_errors.csv"

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"

EVALUATION_HORIZON_PERIODS = 3
IN_SAMPLE_MONTHS = 6
OUT_SAMPLE_MONTHS = 3
SHIFT_MONTHS = 3

MIN_ACTIVE_SIGNALS_OVERALL = 30
MIN_ACTIVE_SIGNALS_SECTOR = 10


VOLUME_VARIANTS = [
    {
        "variant": "SMA10/SMA50 | No Volume Filter",
        "volume_label": "No Volume Filter",
        "use_volume_filter": False,
        "volume_ma_window": None,
        "volume_multiplier": None,
        "signal_column": "MA10_50_NOVOL_Signal",
    },
    {
        "variant": "SMA10/SMA50 | Volume >= 0.8 x VolMA20",
        "volume_label": "Volume >= 0.8 x VolMA20",
        "use_volume_filter": True,
        "volume_ma_window": 20,
        "volume_multiplier": 0.8,
        "signal_column": "MA10_50_VOLMA20_0p8_Signal",
    },
    {
        "variant": "SMA10/SMA50 | Volume >= 0.9 x VolMA20",
        "volume_label": "Volume >= 0.9 x VolMA20",
        "use_volume_filter": True,
        "volume_ma_window": 20,
        "volume_multiplier": 0.9,
        "signal_column": "MA10_50_VOLMA20_0p9_Signal",
    },
    {
        "variant": "SMA10/SMA50 | Volume >= 1.0 x VolMA20",
        "volume_label": "Volume >= 1.0 x VolMA20",
        "use_volume_filter": True,
        "volume_ma_window": 20,
        "volume_multiplier": 1.0,
        "signal_column": "MA10_50_VOLMA20_1p0_Signal",
    },
    {
        "variant": "SMA10/SMA50 | Volume >= 0.8 x VolMA10",
        "volume_label": "Volume >= 0.8 x VolMA10",
        "use_volume_filter": True,
        "volume_ma_window": 10,
        "volume_multiplier": 0.8,
        "signal_column": "MA10_50_VOLMA10_0p8_Signal",
    },
    {
        "variant": "SMA10/SMA50 | Volume >= 0.9 x VolMA10",
        "volume_label": "Volume >= 0.9 x VolMA10",
        "use_volume_filter": True,
        "volume_ma_window": 10,
        "volume_multiplier": 0.9,
        "signal_column": "MA10_50_VOLMA10_0p9_Signal",
    },
    {
        "variant": "SMA10/SMA50 | Volume >= 1.0 x VolMA10",
        "volume_label": "Volume >= 1.0 x VolMA10",
        "use_volume_filter": True,
        "volume_ma_window": 10,
        "volume_multiplier": 1.0,
        "signal_column": "MA10_50_VOLMA10_1p0_Signal",
    },
]


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


def ensure_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    if "SMA10" not in result.columns:
        result["SMA10"] = calculate_sma(result, 10)

    if "SMA50" not in result.columns:
        result["SMA50"] = calculate_sma(result, 50)

    if "Volume_MA20" not in result.columns:
        result["Volume_MA20"] = result["Volume"].rolling(window=20).mean()

    if "Volume_MA10" not in result.columns:
        result["Volume_MA10"] = result["Volume"].rolling(window=10).mean()

    return result


def generate_ma10_50_signal(
    df: pd.DataFrame,
    signal_column: str,
    use_volume_filter: bool,
    volume_ma_window: int | None,
    volume_multiplier: float | None,
) -> pd.DataFrame:
    result = ensure_base_columns(df)
    result[signal_column] = HOLD

    required_columns = ["SMA10", "SMA50", "Volume"]

    if use_volume_filter:
        if volume_ma_window is None or volume_multiplier is None:
            raise ValueError("volume_ma_window dan volume_multiplier wajib diisi jika filter volume aktif.")

        volume_ma_col = f"Volume_MA{volume_ma_window}"
        required_columns.append(volume_ma_col)
    else:
        volume_ma_col = None

    valid = (
        result[required_columns].notna().all(axis=1)
        & result[["SMA10", "SMA50"]].shift(1).notna().all(axis=1)
    )

    bullish_cross = (
        valid
        & (result["SMA10"].shift(1) <= result["SMA50"].shift(1))
        & (result["SMA10"] > result["SMA50"])
    )

    bearish_cross = (
        valid
        & (result["SMA10"].shift(1) >= result["SMA50"].shift(1))
        & (result["SMA10"] < result["SMA50"])
    )

    if use_volume_filter:
        volume_confirmed = result["Volume"] >= result[volume_ma_col] * float(volume_multiplier)
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

        signal_df = ensure_base_columns(combined.copy())

        for variant in VOLUME_VARIANTS:
            signal_df = generate_ma10_50_signal(
                signal_df,
                signal_column=str(variant["signal_column"]),
                use_volume_filter=bool(variant["use_volume_filter"]),
                volume_ma_window=variant["volume_ma_window"],
                volume_multiplier=variant["volume_multiplier"],
            )

        evaluation = signal_df.loc[signal_df.index.isin(out_df.index)].copy()

        for variant in VOLUME_VARIANTS:
            metric = evaluate_signal_performance(
                evaluation,
                str(variant["signal_column"]),
                forward_periods=EVALUATION_HORIZON_PERIODS,
            )

            records.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "window_id": int(window["window_id"]),
                    "indicator": "MA Crossover",
                    "variant": variant["variant"],
                    "volume_label": variant["volume_label"],
                    "use_volume_filter": bool(variant["use_volume_filter"]),
                    "volume_ma_window": variant["volume_ma_window"],
                    "volume_multiplier": variant["volume_multiplier"],
                    "signal_column": variant["signal_column"],
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
        window_df.groupby(group_keys, dropna=False, as_index=False)[
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
            active_windows.groupby(group_keys, dropna=False, as_index=False)["hit_rate"]
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
    print(f"Jumlah varian volume MA10/SMA50 yang diuji: {len(VOLUME_VARIANTS)}")
    print("Mulai menjalankan audit MA10/SMA50 volume filter...\n")

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
        "indicator",
        "variant",
        "volume_label",
        "use_volume_filter",
        "volume_ma_window",
        "volume_multiplier",
        "signal_column",
    ]

    summary_df = aggregate_results(window_df, group_keys)
    summary_df = add_reliability_flag(summary_df, MIN_ACTIVE_SIGNALS_OVERALL)
    summary_df = summary_df.sort_values(
        ["meets_min_active_signals", "directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    sector_group_keys = ["sector", *group_keys]
    sector_df = aggregate_results(window_df, sector_group_keys)
    sector_df = add_reliability_flag(sector_df, MIN_ACTIVE_SIGNALS_SECTOR)
    sector_df = sector_df.sort_values(
        ["sector", "meets_min_active_signals", "directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[True, False, False, False, False],
    ).reset_index(drop=True)
    sector_df.to_csv(SECTOR_OUTPUT_PATH, index=False)

    best_by_sector_df = select_best_by_sector(sector_df)
    best_by_sector_df.to_csv(BEST_BY_SECTOR_OUTPUT_PATH, index=False)

    if errors:
        pd.DataFrame(errors).to_csv(ERROR_OUTPUT_PATH, index=False)

    print("\nAudit MA10/SMA50 volume filter selesai.")
    print(f"Window results     : {WINDOW_OUTPUT_PATH}")
    print(f"Summary aggregate  : {SUMMARY_OUTPUT_PATH}")
    print(f"Sector aggregate   : {SECTOR_OUTPUT_PATH}")
    print(f"Best by sector     : {BEST_BY_SECTOR_OUTPUT_PATH}")

    if errors:
        print(f"Errors             : {ERROR_OUTPUT_PATH}")

    print("\nRingkasan keseluruhan MA10/SMA50 volume filter:")
    print(
        summary_df[
            [
                "variant",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
                "meets_min_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nVarian MA10/SMA50 terbaik per sektor:")
    print(
        best_by_sector_df[
            [
                "sector",
                "variant",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
                "meets_min_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nPerbandingan per sektor seluruh varian:")
    print(
        sector_df[
            [
                "sector",
                "variant",
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