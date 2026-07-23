"""Run fixed-length rolling WFA with in-sample selection and out-of-sample validation."""

# CATATAN FILE:
# File ini berisi script utama untuk menjalankan Fixed-Length Rolling Walk-Forward Analysis.
# Kegunaannya adalah mengevaluasi indikator pada in-sample, memvalidasi indikator terpilih pada out-of-sample, lalu menghasilkan file CSV final untuk skripsi dan aplikasi.


from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
   

from services.data_service import (  # noqa: E402
    END_DATE,
    LAST_EVALUATION_DATE,
    START_DATE,
    WARMUP_START_DATE,
    WARMUP_TRADING_DAYS,
    load_or_fetch_price_data,
)

from services.indicator_service import calculate_all_indicators  # noqa: E402
from services.mapping_service import load_mapping  # noqa: E402
from services.metric_service import evaluate_signal_performance_average_forward  # noqa: E402
from services.signal_service import generate_all_signals  # noqa: E402
from services.wfa_service import INDICATOR_SIGNAL_MAP, generate_wfa_windows, select_best_indicator  # noqa: E402

IN_SAMPLE_MONTHS, OUT_SAMPLE_MONTHS, SHIFT_MONTHS = 6, 3, 3
EVALUATION_HORIZONS = [1, 3, 5, 10]

DATA_DIR = PROJECT_ROOT / "data"
DATE_RANGE_LABEL = f"{START_DATE}_{LAST_EVALUATION_DATE}"

STOCK_PATH = DATA_DIR / f"wfa_stock_results_{DATE_RANGE_LABEL}.csv"
AGGREGATE_PATH = DATA_DIR / f"wfa_sector_aggregate_{DATE_RANGE_LABEL}.csv"
BEST_PATH = DATA_DIR / f"wfa_best_indicator_by_sector_{DATE_RANGE_LABEL}.csv"
SUMMARY_PATH = DATA_DIR / f"wfa_summary_{DATE_RANGE_LABEL}.csv"
WINDOW_PATH = DATA_DIR / f"wfa_window_count_{DATE_RANGE_LABEL}.csv"
WINDOW_RESULTS_PATH = DATA_DIR / f"wfa_window_results_{DATE_RANGE_LABEL}.csv"
SELECTION_PATH = DATA_DIR / f"wfa_sector_window_selection_{DATE_RANGE_LABEL}.csv"

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
    "window_id",
    "period",
    "indicator",
    "signal_column",
    "in_sample_start",
    "in_sample_end",
    "out_sample_start",
    "out_sample_end",
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

SELECTION_COLUMNS = [
    "sektor",
    "window_id",
    "in_sample_start",
    "in_sample_end",
    "out_sample_start",
    "out_sample_end",
    "selected_indicator",
    "selected_signal_column",
    "in_sample_total_stocks",
    "in_sample_total_active_signals",
    "in_sample_correct_signals",
    "in_sample_directional_accuracy",
    "in_sample_hit_rate",
    "out_sample_total_stocks",
    "out_sample_total_active_signals",
    "out_sample_correct_signals",
    "out_sample_directional_accuracy",
    "out_sample_hit_rate",
]


# CATATAN FUNGSI: Membaca argumen command-line untuk menjalankan WFA.
# CARA KERJA SINGKAT: Argumen refresh menentukan apakah data diambil ulang atau memakai cache.
# KEGUNAAN: Dipakai saat menjalankan script WFA final.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run WFA with in-sample indicator selection and out-of-sample validation."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch prices again instead of using cached data.",
    )
    return parser.parse_args()


# CATATAN FUNGSI: Memuat 40 saham sampel penelitian dari mapping.
# CARA KERJA SINGKAT: Mapping difilter lengkap dan sampel, lalu divalidasi harus 4 sektor masing-masing 10 saham.
# KEGUNAAN: Menjamin WFA memakai cakupan penelitian yang terkunci.
def load_samples() -> pd.DataFrame:
    """Load the locked 40-stock research sample from the mapping file."""
    mapping = load_mapping()
    if "is_sample" not in mapping.columns:
        raise ValueError("Kolom is_sample tidak tersedia pada mapping.")

    sample = mapping[
        mapping["status_data"].astype(str).str.strip().str.lower().eq("lengkap")
        & mapping["is_sample"].astype(str).str.strip().str.lower().eq("ya")
    ][["sektor", "ticker", "ticker_yfinance"]].copy()

    counts = sample.groupby("sektor")["ticker"].nunique()
    if len(sample) != 40 or len(counts) != 4 or not counts.eq(10).all():
        raise ValueError(
            "Diperlukan 40 saham pada 4 sektor masing-masing 10; "
            f"ditemukan {len(sample)}, {counts.to_dict()}."
        )

    return sample.sort_values(["sektor", "ticker"]).reset_index(drop=True)


# CATATAN FUNGSI: Menambahkan DA dan merapikan Hit Rate pada hasil agregasi.
# CARA KERJA SINGKAT: DA dihitung dari Correct dibagi Active, sedangkan Hit Rate diisi nol jika kosong.
# KEGUNAAN: Dipakai sebelum hasil WFA disimpan atau dipilih.
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


# CATATAN FUNGSI: Menghitung rata-rata Hit Rate dari unit yang memiliki sinyal aktif.
# CARA KERJA SINGKAT: Baris dengan total_active_signals nol dikeluarkan, lalu hit_rate dirata-ratakan per group.
# KEGUNAAN: Menjelaskan pembagi Unit Aktif pada hasil akhir.
def average_active_hit_rate(df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    active = df[df["total_active_signals"] > 0]
    if active.empty:
        return pd.DataFrame(columns=[*group_keys, "hit_rate"])

    return active.groupby(group_keys, as_index=False)["hit_rate"].mean()


# CATATAN FUNGSI: Mengevaluasi semua indikator pada satu periode WFA.
# CARA KERJA SINGKAT: Setiap kolom sinyal dinilai menggunakan Average Forward Return T+1, T+3, T+5, T+10.
# KEGUNAAN: Dipakai untuk in-sample selection dan out-of-sample validation.
def evaluate_period(
    signal_df: pd.DataFrame,
    period_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    if signal_df.empty or period_df.empty:
        return []

    evaluation = signal_df.loc[signal_df.index.isin(period_df.index)].copy()
    if evaluation.empty:
        return []

    results: list[dict[str, Any]] = []
    for indicator, signal_column in INDICATOR_SIGNAL_MAP.items():
        metric = evaluate_signal_performance_average_forward(
            evaluation,
            signal_column,
            forward_horizons=EVALUATION_HORIZONS,
        )
        results.append(
            {
                "indicator": indicator,
                "signal_column": signal_column,
                "total_active_signals": int(metric["total_active_signals"]),
                "correct_signals": int(metric["correct_signals"]),
                "directional_accuracy": float(metric["directional_accuracy"]),
                "hit_rate": float(metric["hit_rate"]),
            }
        )

    return results


# CATATAN FUNGSI: Mengevaluasi satu saham pada seluruh window WFA.
# CARA KERJA SINGKAT: Data harga dengan warm-up dimuat, window dibuat, indikator/sinyal dihitung, lalu metrik in-sample dan out-sample dicatat.
# KEGUNAAN: Menghasilkan detail WFA per saham-window.
def evaluate_stock_windows(stock: pd.Series, refresh: bool) -> tuple[pd.DataFrame, int]:
    """Evaluate one stock across all WFA windows using warm-up-aware data."""
    price = load_or_fetch_price_data(
        stock["ticker_yfinance"],
        WARMUP_START_DATE,
        END_DATE,
        use_cache=not refresh,
    )

    windows = generate_wfa_windows(
        price,
        IN_SAMPLE_MONTHS,
        OUT_SAMPLE_MONTHS,
        SHIFT_MONTHS,
        evaluation_start_date=START_DATE,
        warmup_periods=WARMUP_TRADING_DAYS,
    )

    records: list[dict[str, Any]] = []

    for window in windows:
        combined_df = window.get("combined_df")
        in_sample_df = window.get("in_sample_df")
        out_sample_df = window.get("out_sample_df")

        if (
            not isinstance(combined_df, pd.DataFrame)
            or combined_df.empty
            or not isinstance(in_sample_df, pd.DataFrame)
            or in_sample_df.empty
            or not isinstance(out_sample_df, pd.DataFrame)
            or out_sample_df.empty
        ):
            continue

        signal_df = generate_all_signals(calculate_all_indicators(combined_df))
        # Indicators are calculated on warm-up + in-sample + out-sample rows,
        # while metrics are measured only on the requested period rows.

        for period, period_df in (
            ("in_sample", in_sample_df),
            ("out_sample", out_sample_df),
        ):
            for metric in evaluate_period(signal_df, period_df):
                records.append(
                    {
                        "sektor": stock["sektor"],
                        "ticker": stock["ticker"],
                        "ticker_yfinance": stock["ticker_yfinance"],
                        "window_id": int(window["window_id"]),
                        "period": period,
                        "indicator": metric["indicator"],
                        "signal_column": metric["signal_column"],
                        "in_sample_start": format_date(window["in_sample_start"]),
                        "in_sample_end": format_date(window["in_sample_end"]),
                        "out_sample_start": format_date(window["out_sample_start"]),
                        "out_sample_end": format_date(window["out_sample_end"]),
                        "total_active_signals": metric["total_active_signals"],
                        "correct_signals": metric["correct_signals"],
                        "directional_accuracy": metric["directional_accuracy"],
                        "hit_rate": metric["hit_rate"],
                    }
                )

    return pd.DataFrame(records, columns=WINDOW_RESULT_COLUMNS), len(windows)


# CATATAN FUNGSI: Mengagregasi hasil saham-window pada level sektor-window-period.
# CARA KERJA SINGKAT: Data dipilih berdasarkan periode, lalu digabung per sektor, window, dan indikator.
# KEGUNAAN: Dipakai untuk seleksi indikator in-sample dan pembacaan performa out-sample.
def aggregate_sector_window_period(window_results: pd.DataFrame, period: str) -> pd.DataFrame:
    source = window_results[window_results["period"] == period].copy()
    if source.empty:
        return pd.DataFrame()

    group_keys = ["sektor", "window_id", "indicator", "signal_column"]

    aggregate = source.groupby(group_keys, as_index=False).agg(
        in_sample_start=("in_sample_start", "first"),
        in_sample_end=("in_sample_end", "first"),
        out_sample_start=("out_sample_start", "first"),
        out_sample_end=("out_sample_end", "first"),
        total_stocks=("ticker", "nunique"),
        total_active_signals=("total_active_signals", "sum"),
        correct_signals=("correct_signals", "sum"),
    )

    aggregate = aggregate.merge(
        average_active_hit_rate(source, group_keys),
        on=group_keys,
        how="left",
    )

    return add_scores(aggregate)


# CATATAN FUNGSI: Memilih indikator terbaik per sektor-window dan mengambil hasil OOS-nya.
# CARA KERJA SINGKAT: Indikator dipilih dari in-sample, lalu metrik indikator yang sama dicari pada out-sample.
# KEGUNAAN: Menjadi inti alur WFA: in-sample selection ke out-of-sample validation.
def build_sector_window_selection(window_results: pd.DataFrame) -> pd.DataFrame:
    """Select the best in-sample indicator per sector-window and attach OOS metrics."""

    in_sample = aggregate_sector_window_period(window_results, "in_sample")
    out_sample = aggregate_sector_window_period(window_results, "out_sample")

    if in_sample.empty or out_sample.empty:
        return pd.DataFrame(columns=SELECTION_COLUMNS)

    selection_records: list[dict[str, Any]] = []

    for (sector, window_id), in_group in in_sample.groupby(["sektor", "window_id"]):
        selected = select_best_indicator(
            in_group[
                [
                    "indicator",
                    "signal_column",
                    "total_active_signals",
                    "correct_signals",
                    "directional_accuracy",
                    "hit_rate",
                ]
            ]
        )
        if not selected:
            continue

        selected_indicator = str(selected["indicator"])
        in_row = in_group[in_group["indicator"] == selected_indicator].iloc[0]

        out_group = out_sample[
            (out_sample["sektor"] == sector)
            & (out_sample["window_id"] == window_id)
            & (out_sample["indicator"] == selected_indicator)
        ]
        if out_group.empty:
            continue

        out_row = out_group.iloc[0]

        selection_records.append(
            {
                "sektor": sector,
                "window_id": int(window_id),
                "in_sample_start": in_row["in_sample_start"],
                "in_sample_end": in_row["in_sample_end"],
                "out_sample_start": in_row["out_sample_start"],
                "out_sample_end": in_row["out_sample_end"],
                "selected_indicator": selected_indicator,
                "selected_signal_column": selected["signal_column"],
                "in_sample_total_stocks": int(in_row["total_stocks"]),
                "in_sample_total_active_signals": int(in_row["total_active_signals"]),
                "in_sample_correct_signals": int(in_row["correct_signals"]),
                "in_sample_directional_accuracy": float(in_row["directional_accuracy"]),
                "in_sample_hit_rate": float(in_row["hit_rate"]),
                "out_sample_total_stocks": int(out_row["total_stocks"]),
                "out_sample_total_active_signals": int(out_row["total_active_signals"]),
                "out_sample_correct_signals": int(out_row["correct_signals"]),
                "out_sample_directional_accuracy": float(out_row["directional_accuracy"]),
                "out_sample_hit_rate": float(out_row["hit_rate"]),
            }
        )

    return pd.DataFrame(selection_records, columns=SELECTION_COLUMNS)


# CATATAN FUNGSI: Mengambil hanya baris OOS indikator yang terpilih dari in-sample.
# CARA KERJA SINGKAT: Selection key digabungkan dengan out-sample window results.
# KEGUNAAN: Dipakai agar agregasi akhir hanya memakai indikator yang memang terpilih.
def build_selected_oos_stock_results(
    window_results: pd.DataFrame,
    selection: pd.DataFrame,
) -> pd.DataFrame:
    """Keep only out-sample rows whose indicator was selected from in-sample."""

    if window_results.empty or selection.empty:
        return pd.DataFrame(columns=WINDOW_RESULT_COLUMNS)

    selection_key = selection[
        ["sektor", "window_id", "selected_indicator"]
    ].rename(columns={"selected_indicator": "indicator"})

    out_sample = window_results[window_results["period"] == "out_sample"].copy()
    return out_sample.merge(selection_key, on=["sektor", "window_id", "indicator"], how="inner")


# CATATAN FUNGSI: Mengagregasi hasil OOS terpilih pada level saham.
# CARA KERJA SINGKAT: Baris selected OOS dikelompokkan per sektor, ticker, dan indikator untuk menghitung Active, Correct, DA, dan Hit Rate.
# KEGUNAAN: Dipakai untuk tabel kontribusi per saham.
def aggregate_stock_results(selected_oos: pd.DataFrame) -> pd.DataFrame:
    if selected_oos.empty:
        return pd.DataFrame(columns=STOCK_COLUMNS)

    group_keys = ["sektor", "ticker", "ticker_yfinance", "indicator", "signal_column"]

    stock_results = selected_oos.groupby(group_keys, as_index=False).agg(
        windows_count=("window_id", "count"),
        total_active_signals=("total_active_signals", "sum"),
        correct_signals=("correct_signals", "sum"),
    )
    stock_results = stock_results.merge(
        average_active_hit_rate(selected_oos, group_keys),
        on=group_keys,
        how="left",
    )

    return add_scores(stock_results)[STOCK_COLUMNS]


# CATATAN FUNGSI: Mengagregasi hasil OOS terpilih pada level sektor.
# CARA KERJA SINGKAT: Selected OOS dikelompokkan per sektor dan indikator, lalu baris indikator kosong dilengkapi.
# KEGUNAAN: Dipakai untuk file agregat sektor final.
def aggregate_sector_from_selected_oos(selected_oos: pd.DataFrame, sectors: list[str]) -> pd.DataFrame:
    group_keys = ["sektor", "indicator", "signal_column"]

    if selected_oos.empty:
        aggregate = pd.DataFrame(columns=AGGREGATE_COLUMNS)
    else:
        aggregate = selected_oos.groupby(group_keys, as_index=False).agg(
            total_stocks=("ticker", "nunique"),
            total_windows=("window_id", "count"),
            total_active_signals=("total_active_signals", "sum"),
            correct_signals=("correct_signals", "sum"),
        )
        aggregate = aggregate.merge(
            average_active_hit_rate(selected_oos, group_keys),
            on=group_keys,
            how="left",
        )
        aggregate = add_scores(aggregate)[AGGREGATE_COLUMNS]

    return ensure_all_sector_indicator_rows(aggregate, sectors)


# CATATAN FUNGSI: Memastikan setiap sektor memiliki baris untuk semua indikator.
# CARA KERJA SINGKAT: Jika indikator tidak muncul pada selected OOS, baris nol ditambahkan.
# KEGUNAAN: Membuat tabel output tetap lengkap dan konsisten.
def ensure_all_sector_indicator_rows(aggregate: pd.DataFrame, sectors: list[str]) -> pd.DataFrame:
    existing = {
        (str(row.sektor), str(row.indicator))
        for row in aggregate.itertuples()
    } if not aggregate.empty else set()

    rows = []
    for sector in sectors:
        for indicator, signal_column in INDICATOR_SIGNAL_MAP.items():
            if (str(sector), str(indicator)) not in existing:
                rows.append(
                    {
                        "sektor": sector,
                        "indicator": indicator,
                        "signal_column": signal_column,
                        "total_stocks": 0,
                        "total_windows": 0,
                        "total_active_signals": 0,
                        "correct_signals": 0,
                        "directional_accuracy": 0.0,
                        "hit_rate": 0.0,
                    }
                )

    if rows:
        aggregate = pd.concat([aggregate, pd.DataFrame(rows)], ignore_index=True)

    return aggregate.sort_values(["sektor", "indicator"]).reset_index(drop=True)[AGGREGATE_COLUMNS]


# CATATAN FUNGSI: Memilih indikator terbaik akhir untuk setiap sektor.
# CARA KERJA SINGKAT: Data diurutkan berdasarkan DA, Hit Rate, dan Total Active Signals lalu diambil satu per sektor.
# KEGUNAAN: Dipakai untuk file best indicator by sector.
def select_best_by_sector(aggregate: pd.DataFrame) -> pd.DataFrame:
    if aggregate.empty:
        return pd.DataFrame(columns=AGGREGATE_COLUMNS)

    best = (
        aggregate.sort_values(
            ["sektor", "directional_accuracy", "hit_rate", "total_active_signals"],
            ascending=[True, False, False, False],
        )
        .groupby("sektor", as_index=False)
        .first()
    )

    return best[AGGREGATE_COLUMNS]


# CATATAN FUNGSI: Membuat ringkasan hasil WFA lintas sektor.
# CARA KERJA SINGKAT: Fungsi menghitung jumlah sektor, rata-rata/weighted accuracy, total sinyal, dan daftar indikator terbaik.
# KEGUNAAN: Dipakai untuk file summary hasil akhir.
def build_summary(best: pd.DataFrame) -> pd.DataFrame:
    active = int(best["total_active_signals"].sum())
    correct = int(best["correct_signals"].sum())

    return pd.DataFrame(
        [
            {
                "sectors_count": best["sektor"].nunique(),
                "sectors_above_50": int((best["directional_accuracy"] > 50).sum()),
                "average_best_accuracy": best["directional_accuracy"].mean(),
                "weighted_best_accuracy": 0.0 if active == 0 else correct / active * 100,
                "total_active_signals": active,
                "correct_signals": correct,
                "min_sector_accuracy": best["directional_accuracy"].min(),
                "max_sector_accuracy": best["directional_accuracy"].max(),
                "best_indicators_by_sector": "; ".join(
                    f"{row.sektor}: {row.indicator}" for row in best.itertuples()
                ),
            }
        ]
    )


# CATATAN FUNGSI: Mengubah nilai tanggal menjadi string YYYY-MM-DD.
# CARA KERJA SINGKAT: Nilai dikonversi ke pandas Timestamp lalu diformat.
# KEGUNAAN: Dipakai saat menulis batas window WFA ke CSV.
def format_date(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


# CATATAN FUNGSI: Menjalankan pipeline WFA final dari awal sampai output CSV.
# CARA KERJA SINGKAT: Fungsi memuat sampel, mengevaluasi saham, membangun selection, selected OOS, agregat, best indicator, summary, lalu menyimpan file.
# KEGUNAAN: Dipakai sebagai entry point utama pembentukan hasil WFA skripsi.
def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    samples = load_samples()
    window_frames = []
    window_counts = []

    print(
        f"Jumlah saham: {len(samples)}\n"
        f"Jumlah sektor: {samples.sektor.nunique()}\n"
        f"Periode evaluasi: {START_DATE} s.d. {LAST_EVALUATION_DATE}\n"
        f"Warm-up data mulai: {WARMUP_START_DATE}, maksimum {WARMUP_TRADING_DAYS} hari perdagangan\n"
        f"WFA: {IN_SAMPLE_MONTHS},{OUT_SAMPLE_MONTHS},{SHIFT_MONTHS}\n"
        f"Evaluasi: Average Forward Return T+1, T+3, T+5, T+10\n"
        "Alur: In-Sample selection -> Out-of-Sample validation"
    )

    for position, (_, stock) in enumerate(samples.iterrows(), 1):
        print(f"[{position}/40] {stock.sektor} - {stock.ticker}")
        window_result, count = evaluate_stock_windows(stock, args.refresh)

        if window_result.empty:
            raise RuntimeError(f"Hasil WFA kosong untuk {stock.ticker}.")

        window_frames.append(window_result)
        window_counts.append(
            {
                "sektor": stock.sektor,
                "ticker": stock.ticker,
                "ticker_yfinance": stock.ticker_yfinance,
                "windows_count": count,
            }
        )

    window_results = pd.concat(window_frames, ignore_index=True)
    window_results = window_results.sort_values(
        ["sektor", "ticker", "window_id", "period", "indicator"]
    )[WINDOW_RESULT_COLUMNS]

    selection = build_sector_window_selection(window_results)
    if selection.empty:
        raise RuntimeError("Hasil seleksi WFA per sektor kosong.")

    selected_oos = build_selected_oos_stock_results(window_results, selection)
    if selected_oos.empty:
        raise RuntimeError("Hasil validasi OOS indikator terpilih kosong.")

    sectors = sorted(samples["sektor"].unique())
    stock_results = aggregate_stock_results(selected_oos)
    aggregate = aggregate_sector_from_selected_oos(selected_oos, sectors)
    best = select_best_by_sector(aggregate)
    summary = build_summary(best)
    window_count_df = pd.DataFrame(window_counts)

    stock_results.to_csv(STOCK_PATH, index=False)
    window_results.to_csv(WINDOW_RESULTS_PATH, index=False)
    selection_export = selection.drop(
        columns=["in_sample_hit_rate","out_sample_hit_rate"],
        errors="ignore",
    )

    selection_export.to_csv(SELECTION_PATH, index=False)
    aggregate.to_csv(AGGREGATE_PATH, index=False)
    best.to_csv(BEST_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    window_count_df.to_csv(WINDOW_PATH, index=False)

    print("\nJumlah window per saham:")
    print(window_count_df.to_string(index=False))

    print("\nSeleksi indikator per sektor-window:")
    print(
        selection[
            [
                "sektor",
                "window_id",
                "selected_indicator",
                "in_sample_directional_accuracy",
                "out_sample_directional_accuracy",
                "out_sample_total_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nBest indicator per sector:")
    print(
        best[
            [
                "sektor",
                "indicator",
                "directional_accuracy",
                "hit_rate",
                "total_active_signals",
            ]
        ].to_string(index=False)
    )

    print("\nRingkasan WFA:")
    print(summary.to_string(index=False))

    print("\nOutput:")
    for path in (
        STOCK_PATH,
        WINDOW_RESULTS_PATH,
        SELECTION_PATH,
        AGGREGATE_PATH,
        BEST_PATH,
        SUMMARY_PATH,
        WINDOW_PATH,
    ):
        print(path)


if __name__ == "__main__":
    main()
    """Run the final WFA pipeline and write all thesis CSV outputs."""