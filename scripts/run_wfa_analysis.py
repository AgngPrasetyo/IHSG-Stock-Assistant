"""Run the main fixed-length rolling WFA analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.data_service import END_DATE, START_DATE, load_or_fetch_price_data
from services.mapping_service import load_mapping
from services.wfa_service import generate_wfa_windows, run_wfa_pipeline

IN_SAMPLE_MONTHS, OUT_SAMPLE_MONTHS, SHIFT_MONTHS = 6, 3, 3
EVALUATION_HORIZON_PERIODS = 3

DATA_DIR = PROJECT_ROOT / "data"
DATE_RANGE_LABEL = f"{START_DATE}_{END_DATE}"

STOCK_PATH = DATA_DIR / f"wfa_stock_results_{DATE_RANGE_LABEL}.csv"
AGGREGATE_PATH = DATA_DIR / f"wfa_sector_aggregate_{DATE_RANGE_LABEL}.csv"
BEST_PATH = DATA_DIR / f"wfa_best_indicator_by_sector_{DATE_RANGE_LABEL}.csv"
SUMMARY_PATH = DATA_DIR / f"wfa_summary_{DATE_RANGE_LABEL}.csv"
WINDOW_PATH = DATA_DIR / f"wfa_window_count_{DATE_RANGE_LABEL}.csv"
WINDOW_RESULTS_PATH = DATA_DIR / f"wfa_window_results_{DATE_RANGE_LABEL}.csv"

STOCK_COLUMNS = [
    "sektor",
    "ticker",
    "ticker_yfinance",
    "indicator",
    "signal_column",
    "windows_count",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
]

WINDOW_RESULT_COLUMNS = [
    "sektor",
    "ticker",
    "ticker_yfinance",
    "indicator",
    "signal_column",
    "window_id",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
]

AGGREGATE_COLUMNS = [
    "sektor",
    "indicator",
    "signal_column",
    "total_stocks",
    "total_windows",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the main WFA analysis.")
    parser.add_argument("--refresh", action="store_true", help="Fetch prices again instead of using cached data.")
    return parser.parse_args()


def load_samples() -> pd.DataFrame:
    mapping = load_mapping()
    if "is_sample" not in mapping.columns:
        raise ValueError("Kolom is_sample tidak tersedia pada mapping.")
    sample = mapping[
        mapping["status_data"].astype(str).str.strip().str.lower().eq("lengkap")
        & mapping["is_sample"].astype(str).str.strip().str.lower().eq("ya")
    ][["sektor", "ticker", "ticker_yfinance"]].copy()
    counts = sample.groupby("sektor")["ticker"].nunique()
    if len(sample) != 40 or len(counts) != 4 or not counts.eq(10).all():
        raise ValueError(f"Diperlukan 40 saham pada 4 sektor masing-masing 10; ditemukan {len(sample)}, {counts.to_dict()}.")
    return sample.sort_values(["sektor", "ticker"]).reset_index(drop=True)


def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["directional_accuracy"] = 0.0
    active = result["total_active_signals"] > 0
    result.loc[active, "directional_accuracy"] = (
        result.loc[active, "correct_signals"]
        / result.loc[active, "total_active_signals"]
        * 100
    )
    if "hit_rate" not in result.columns:
        result["hit_rate"] = 0.0
    result["hit_rate"] = result["hit_rate"].fillna(0.0)
    return result


def average_active_hit_rate(df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    active = df[df["total_active_signals"] > 0]
    if active.empty:
        return pd.DataFrame(columns=[*group_keys, "hit_rate"])
    return active.groupby(group_keys, as_index=False)["hit_rate"].mean()


def evaluate_stock(stock: pd.Series, refresh: bool) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    price = load_or_fetch_price_data(
        stock["ticker_yfinance"],
        START_DATE,
        END_DATE,
        use_cache=not refresh,
    )
    windows = generate_wfa_windows(price, IN_SAMPLE_MONTHS, OUT_SAMPLE_MONTHS, SHIFT_MONTHS)
    wfa = run_wfa_pipeline(
        price,
        EVALUATION_HORIZON_PERIODS,
        IN_SAMPLE_MONTHS,
        OUT_SAMPLE_MONTHS,
        SHIFT_MONTHS,
    )

    stock_results = wfa["aggregate_results"].copy()
    if stock_results.empty:
        return pd.DataFrame(), pd.DataFrame(), len(windows)
    stock_results["sektor"] = stock["sektor"]
    stock_results["ticker"] = stock["ticker"]
    stock_results["ticker_yfinance"] = stock["ticker_yfinance"]
    stock_results["windows_count"] = int(wfa.get("windows_count", len(windows)))

    window_results = wfa["wfa_results"].copy()
    window_results["sektor"] = stock["sektor"]
    window_results["ticker"] = stock["ticker"]
    window_results["ticker_yfinance"] = stock["ticker_yfinance"]

    return (
        stock_results[STOCK_COLUMNS],
        window_results[WINDOW_RESULT_COLUMNS],
        len(windows),
    )


def aggregate_sector_from_windows(window_results: pd.DataFrame) -> pd.DataFrame:
    if window_results.empty:
        return pd.DataFrame(columns=AGGREGATE_COLUMNS)

    sector_keys = ["sektor", "indicator", "signal_column"]
    aggregate = window_results.groupby(sector_keys, as_index=False).agg(
        total_stocks=("ticker", "nunique"),
        total_windows=("window_id", "count"),
        total_active_signals=("total_active_signals", "sum"),
        correct_signals=("correct_signals", "sum"),
    )
    aggregate = aggregate.merge(
        average_active_hit_rate(window_results, sector_keys),
        on=sector_keys,
        how="left",
    )
    return add_scores(aggregate)[AGGREGATE_COLUMNS]


def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    samples, stock_frames, window_frames, windows = load_samples(), [], [], []
    print(f"Jumlah saham: {len(samples)}\nJumlah sektor: {samples.sektor.nunique()}\nPeriode data: {START_DATE} s.d. {END_DATE} (exclusive)\nWFA: {IN_SAMPLE_MONTHS},{OUT_SAMPLE_MONTHS},{SHIFT_MONTHS}\nHorizon evaluasi: {EVALUATION_HORIZON_PERIODS}")
    for position, (_, stock) in enumerate(samples.iterrows(), 1):
        print(f"[{position}/40] {stock.sektor} - {stock.ticker}")
        stock_result, window_result, count = evaluate_stock(stock, args.refresh)
        if stock_result.empty or window_result.empty:
            raise RuntimeError(f"Hasil WFA kosong untuk {stock.ticker}.")
        stock_frames.append(stock_result)
        window_frames.append(window_result)
        windows.append({"sektor": stock.sektor, "ticker": stock.ticker, "ticker_yfinance": stock.ticker_yfinance, "windows_count": count})

    stock_results = pd.concat(stock_frames, ignore_index=True).sort_values(["sektor", "ticker", "indicator"])
    stock_results = stock_results[STOCK_COLUMNS]
    window_results = pd.concat(window_frames, ignore_index=True).sort_values(["sektor", "ticker", "indicator", "window_id"])
    window_results = window_results[WINDOW_RESULT_COLUMNS]
    aggregate = aggregate_sector_from_windows(window_results)
    best = aggregate.sort_values(["sektor", "directional_accuracy", "hit_rate", "total_active_signals"], ascending=[True, False, False, False]).groupby("sektor", as_index=False).first()
    best = best[AGGREGATE_COLUMNS]
    active, correct = int(best.total_active_signals.sum()), int(best.correct_signals.sum())
    summary = pd.DataFrame([{"sectors_count": best.sektor.nunique(), "sectors_above_50": int((best.directional_accuracy > 50).sum()), "average_best_accuracy": best.directional_accuracy.mean(), "weighted_best_accuracy": 0.0 if active == 0 else correct / active * 100, "total_active_signals": active, "correct_signals": correct, "min_sector_accuracy": best.directional_accuracy.min(), "max_sector_accuracy": best.directional_accuracy.max(), "best_indicators_by_sector": "; ".join(f"{x.sektor}: {x.indicator}" for x in best.itertuples())}])
    window_counts = pd.DataFrame(windows)
    stock_results.to_csv(STOCK_PATH, index=False); window_results.to_csv(WINDOW_RESULTS_PATH, index=False); aggregate.to_csv(AGGREGATE_PATH, index=False); best.to_csv(BEST_PATH, index=False); summary.to_csv(SUMMARY_PATH, index=False); window_counts.to_csv(WINDOW_PATH, index=False)
    print("\nJumlah window per saham:"); print(window_counts.to_string(index=False))
    print("\nBest indicator per sector:"); print(best[["sektor", "indicator", "directional_accuracy", "hit_rate", "total_active_signals"]].to_string(index=False))
    print("\nRingkasan WFA:"); print(summary.to_string(index=False))
    print("\nOutput:"); [print(path) for path in (STOCK_PATH, WINDOW_RESULTS_PATH, AGGREGATE_PATH, BEST_PATH, SUMMARY_PATH, WINDOW_PATH)]


if __name__ == "__main__":
    main()
