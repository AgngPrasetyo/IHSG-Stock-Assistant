from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from services.data_service import REQUIRED_OHLCV_COLUMNS, load_or_fetch_price_data  # noqa: E402
from services.indicator_service import calculate_rsi, calculate_sma  # noqa: E402
from services.mapping_service import load_mapping  # noqa: E402
from services.metric_service import evaluate_signal_performance  # noqa: E402
from services.wfa_service import generate_wfa_windows  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "data"

WINDOW_OUTPUT_PATH = OUTPUT_DIR / "audit_rsi_without_sma50_wfa_window_results.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "audit_rsi_without_sma50_wfa_summary.csv"
SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_rsi_without_sma50_wfa_sector_aggregate.csv"
BEST_OVERALL_OUTPUT_PATH = OUTPUT_DIR / "audit_rsi_without_sma50_wfa_best_overall.csv"
BEST_BY_SECTOR_OUTPUT_PATH = OUTPUT_DIR / "audit_rsi_without_sma50_wfa_best_by_sector.csv"
ERROR_OUTPUT_PATH = OUTPUT_DIR / "audit_rsi_without_sma50_wfa_errors.csv"

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"

EVALUATION_HORIZON_PERIODS = 3
IN_SAMPLE_MONTHS = 6
OUT_SAMPLE_MONTHS = 3
SHIFT_MONTHS = 3

MIN_ACTIVE_SIGNALS_OVERALL = 30
MIN_ACTIVE_SIGNALS_SECTOR = 10


RSI_LEVEL_CONFIGS = [
    {"level_label": "RSI 30/70", "lower_level": 30, "upper_level": 70},
    {"level_label": "RSI 35/65", "lower_level": 35, "upper_level": 65},
    {"level_label": "RSI 25/75", "lower_level": 25, "upper_level": 75},
    {"level_label": "RSI 40/60", "lower_level": 40, "upper_level": 60},
]

SMA50_FILTER_CONFIGS = [
    {"sma50_label": "With SMA50 Filter", "use_sma50_filter": True},
    {"sma50_label": "Without SMA50 Filter", "use_sma50_filter": False},
]

CANDLE_CONFIGS = [
    {"candle_label": "No Candle Confirmation", "use_candle_confirmation": False},
    {"candle_label": "Candle Confirmation", "use_candle_confirmation": True},
]

VOLUME_CONFIGS = [
    {
        "volume_label": "No Volume Filter",
        "use_volume_filter": False,
        "volume_window": 20,
        "volume_multiplier": 0.0,
    },
    {
        "volume_label": "Volume >= VolMA20",
        "use_volume_filter": True,
        "volume_window": 20,
        "volume_multiplier": 1.0,
    },
]


def build_rsi_variant_configs() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []

    for level in RSI_LEVEL_CONFIGS:
        for sma50_filter in SMA50_FILTER_CONFIGS:
            for candle in CANDLE_CONFIGS:
                for volume in VOLUME_CONFIGS:
                    lower_level = int(level["lower_level"])
                    upper_level = int(level["upper_level"])
                    use_sma50_filter = bool(sma50_filter["use_sma50_filter"])
                    use_candle_confirmation = bool(candle["use_candle_confirmation"])
                    use_volume_filter = bool(volume["use_volume_filter"])

                    sma50_code = "SMA50" if use_sma50_filter else "NOSMA50"
                    candle_code = "CANDLE" if use_candle_confirmation else "NOCANDLE"
                    volume_code = "VOL" if use_volume_filter else "NOVOL"

                    variant_name = (
                        f'RSI14 | {level["level_label"]} | '
                        f'{sma50_filter["sma50_label"]} | '
                        f'{candle["candle_label"]} | '
                        f'{volume["volume_label"]}'
                    )

                    signal_column = (
                        f"RSI_{lower_level}_{upper_level}_"
                        f"{sma50_code}_{candle_code}_{volume_code}_Signal"
                    )

                    variants.append(
                        {
                            "indicator": "RSI",
                            "variant": variant_name,
                            "level_label": level["level_label"],
                            "lower_level": lower_level,
                            "upper_level": upper_level,
                            "sma50_label": sma50_filter["sma50_label"],
                            "use_sma50_filter": use_sma50_filter,
                            "candle_label": candle["candle_label"],
                            "use_candle_confirmation": use_candle_confirmation,
                            "volume_label": volume["volume_label"],
                            "use_volume_filter": use_volume_filter,
                            "volume_window": int(volume["volume_window"]),
                            "volume_multiplier": float(volume["volume_multiplier"]),
                            "signal_column": signal_column,
                        }
                    )

    return variants


RSI_VARIANTS = build_rsi_variant_configs()


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

    if "RSI" not in result.columns:
        result = calculate_rsi(result, 14)

    if "SMA50" not in result.columns:
        result["SMA50"] = calculate_sma(result, 50)

    if "Volume_MA20" not in result.columns:
        result["Volume_MA20"] = result["Volume"].rolling(window=20).mean()

    return result


def generate_rsi_variant_signal(
    df: pd.DataFrame,
    signal_column: str,
    lower_level: int,
    upper_level: int,
    use_sma50_filter: bool,
    use_candle_confirmation: bool,
    use_volume_filter: bool,
    volume_window: int = 20,
    volume_multiplier: float = 1.0,
) -> pd.DataFrame:
    result = ensure_base_indicators(df)
    result[signal_column] = HOLD

    volume_ma_col = f"Volume_MA{volume_window}"

    required_columns = ["Close", "RSI"]
    if use_sma50_filter:
        required_columns.append("SMA50")
    if use_volume_filter:
        required_columns.extend(["Volume", volume_ma_col])

    valid = (
        result[required_columns].notna().all(axis=1)
        & result[["RSI", "Close"]].shift(1).notna().all(axis=1)
    )

    buy_signal = (
        valid
        & (result["RSI"].shift(1) < lower_level)
        & (result["RSI"] >= lower_level)
    )

    sell_signal = (
        valid
        & (result["RSI"].shift(1) > upper_level)
        & (result["RSI"] <= upper_level)
    )

    if use_sma50_filter:
        buy_signal = buy_signal & (result["Close"] > result["SMA50"])
        sell_signal = sell_signal & (result["Close"] < result["SMA50"])

    if use_candle_confirmation:
        buy_signal = buy_signal & (result["Close"] > result["Close"].shift(1))
        sell_signal = sell_signal & (result["Close"] < result["Close"].shift(1))

    if use_volume_filter:
        volume_confirmed = result["Volume"] >= result[volume_ma_col] * volume_multiplier
        buy_signal = buy_signal & volume_confirmed
        sell_signal = sell_signal & volume_confirmed

    result.loc[buy_signal, signal_column] = BUY
    result.loc[sell_signal, signal_column] = SELL

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

        signal_df = ensure_base_indicators(combined.copy())

        for variant in RSI_VARIANTS:
            signal_df = generate_rsi_variant_signal(
                signal_df,
                signal_column=str(variant["signal_column"]),
                lower_level=int(variant["lower_level"]),
                upper_level=int(variant["upper_level"]),
                use_sma50_filter=bool(variant["use_sma50_filter"]),
                use_candle_confirmation=bool(variant["use_candle_confirmation"]),
                use_volume_filter=bool(variant["use_volume_filter"]),
                volume_window=int(variant["volume_window"]),
                volume_multiplier=float(variant["volume_multiplier"]),
            )

        evaluation = signal_df.loc[signal_df.index.isin(out_df.index)].copy()

        for variant in RSI_VARIANTS:
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
                    "indicator": "RSI",
                    "variant": variant["variant"],
                    "signal_column": signal_column,
                    "level_label": variant["level_label"],
                    "lower_level": int(variant["lower_level"]),
                    "upper_level": int(variant["upper_level"]),
                    "sma50_label": variant["sma50_label"],
                    "use_sma50_filter": bool(variant["use_sma50_filter"]),
                    "candle_label": variant["candle_label"],
                    "use_candle_confirmation": bool(variant["use_candle_confirmation"]),
                    "volume_label": variant["volume_label"],
                    "use_volume_filter": bool(variant["use_volume_filter"]),
                    "volume_window": int(variant["volume_window"]),
                    "volume_multiplier": float(variant["volume_multiplier"]),
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


def select_best_overall(summary_df: pd.DataFrame) -> pd.DataFrame:
    reliable = summary_df[
        summary_df["total_active_signals"] >= MIN_ACTIVE_SIGNALS_OVERALL
    ].copy()

    if reliable.empty:
        reliable = summary_df.copy()

    return reliable.sort_values(
        ["directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False],
    ).head(15).reset_index(drop=True)


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
    print(f"Jumlah varian RSI yang diuji: {len(RSI_VARIANTS)}")
    print("Mulai menjalankan audit RSI tanpa dan dengan SMA50...\n")

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
        "level_label",
        "lower_level",
        "upper_level",
        "sma50_label",
        "use_sma50_filter",
        "candle_label",
        "use_candle_confirmation",
        "volume_label",
        "use_volume_filter",
        "volume_window",
        "volume_multiplier",
    ]

    summary_df = aggregate_results(window_df, group_keys)
    summary_df = add_reliability_flag(summary_df, MIN_ACTIVE_SIGNALS_OVERALL)
    summary_df = summary_df.sort_values(
        [
            "meets_min_active_signals",
            "directional_accuracy",
            "hit_rate",
            "total_active_signals",
        ],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    summary_df.to_csv(SUMMARY_OUTPUT_PATH, index=False)

    sector_group_keys = ["sector", *group_keys]
    sector_df = aggregate_results(window_df, sector_group_keys)
    sector_df = add_reliability_flag(sector_df, MIN_ACTIVE_SIGNALS_SECTOR)
    sector_df = sector_df.sort_values(
        [
            "sector",
            "meets_min_active_signals",
            "directional_accuracy",
            "hit_rate",
            "total_active_signals",
        ],
        ascending=[True, False, False, False, False],
    ).reset_index(drop=True)
    sector_df.to_csv(SECTOR_OUTPUT_PATH, index=False)

    best_overall_df = select_best_overall(summary_df)
    best_overall_df.to_csv(BEST_OVERALL_OUTPUT_PATH, index=False)

    best_by_sector_df = select_best_by_sector(sector_df)
    best_by_sector_df.to_csv(BEST_BY_SECTOR_OUTPUT_PATH, index=False)

    if errors:
        pd.DataFrame(errors).to_csv(ERROR_OUTPUT_PATH, index=False)

    print("\nAudit RSI tanpa dan dengan SMA50 selesai.")
    print(f"Window results       : {WINDOW_OUTPUT_PATH}")
    print(f"Summary aggregate    : {SUMMARY_OUTPUT_PATH}")
    print(f"Sector aggregate     : {SECTOR_OUTPUT_PATH}")
    print(f"Best overall top 15  : {BEST_OVERALL_OUTPUT_PATH}")
    print(f"Best by sector       : {BEST_BY_SECTOR_OUTPUT_PATH}")

    if errors:
        print(f"Errors               : {ERROR_OUTPUT_PATH}")

    print("\nTop 15 RSI keseluruhan:")
    print(
        best_overall_df[
            [
                "level_label",
                "sma50_label",
                "candle_label",
                "volume_label",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
                "meets_min_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nRSI terbaik per sektor:")
    print(
        best_by_sector_df[
            [
                "sector",
                "level_label",
                "sma50_label",
                "candle_label",
                "volume_label",
                "total_active_signals",
                "correct_signals",
                "directional_accuracy",
                "hit_rate",
                "meets_min_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nPerbandingan ringkas With SMA50 vs Without SMA50:")
    comparison_df = (
        summary_df.groupby("sma50_label", as_index=False)[
            ["total_active_signals", "correct_signals"]
        ]
        .sum()
        .reset_index(drop=True)
    )

    comparison_df["directional_accuracy"] = comparison_df.apply(
        lambda row: (
            int(row["correct_signals"]) / int(row["total_active_signals"]) * 100
            if int(row["total_active_signals"]) > 0
            else 0.0
        ),
        axis=1,
    )

    print(comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()