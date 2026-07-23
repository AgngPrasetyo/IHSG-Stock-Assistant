"""Signal evaluation metrics for deterministic technical analysis."""

# CATATAN FILE:
# File ini berisi perhitungan metrik evaluasi sinyal teknikal.
# Kegunaannya adalah menghitung forward return, Average Forward Return, arah harga aktual, Directional Accuracy, Hit Rate, Total Active Signals, dan Correct Signals yang dipakai dalam evaluasi indikator.


from __future__ import annotations

import pandas as pd

from services.signal_service import (
    MA_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)

FORWARD_RETURN_COLUMN = "Forward_Return"
AVERAGE_FORWARD_RETURN_COLUMN = "Average_Forward_Return"
ACTUAL_DIRECTION_COLUMN = "Actual_Direction"

ACTIVE_SIGNALS = {"BUY", "SELL"}
DEFAULT_FORWARD_HORIZONS = [1, 3, 5, 10]

SIGNAL_COLUMNS = [
    MA_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
]


# CATATAN FUNGSI: Menghitung forward return untuk satu horizon ke depan.
# CARA KERJA SINGKAT: Data disalin, divalidasi, lalu harga Close masa depan dibandingkan dengan Close saat ini.
# KEGUNAAN: Dipakai untuk evaluasi arah harga pada metode lama atau single horizon.
def calculate_forward_return(
    df: pd.DataFrame,
    close_column: str = "Close",
    forward_periods: int = 1,
) -> pd.DataFrame:
    """Add forward return based on one future closing-price horizon."""
    _validate_forward_periods(forward_periods)
    metric_df = _prepare_metric_dataframe(df)
    _validate_column(metric_df, close_column)

    metric_df[FORWARD_RETURN_COLUMN] = (
        metric_df[close_column].shift(-forward_periods) - metric_df[close_column]
    ) / metric_df[close_column]
    return metric_df


# CATATAN FUNGSI: Menghitung Average Forward Return dari beberapa horizon evaluasi.
# CARA KERJA SINGKAT: Return dihitung pada T+1, T+3, T+5, dan T+10 lalu dirata-ratakan hanya jika seluruh horizon tersedia.
# KEGUNAAN: Menjadi dasar evaluasi utama sinyal BUY/SELL dalam penelitian.
def calculate_average_forward_return(
    df: pd.DataFrame,
    close_column: str = "Close",
    forward_horizons: list[int] | tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """
    Add average forward return based on multiple future closing-price horizons.

    A row is evaluable only when all selected horizons are available.
    Default horizons: T+1, T+3, T+5, and T+10 trading days.
    """
    horizons = _normalize_forward_horizons(forward_horizons)
    metric_df = _prepare_metric_dataframe(df)
    _validate_column(metric_df, close_column)

    return_columns = []
    for horizon in horizons:
        column = f"Forward_Return_T{horizon}"
        metric_df[column] = (
            metric_df[close_column].shift(-horizon) - metric_df[close_column]
        ) / metric_df[close_column]
        return_columns.append(column)

    metric_df[AVERAGE_FORWARD_RETURN_COLUMN] = metric_df[return_columns].mean(
        axis=1,
        skipna=False,
    )

    return metric_df


# CATATAN FUNGSI: Menentukan arah harga aktual dari forward return satu horizon.
# CARA KERJA SINGKAT: Forward return positif diberi label UP, negatif DOWN, nol FLAT, dan data tidak tersedia UNKNOWN.
# KEGUNAAN: Dipakai untuk kompatibilitas evaluasi lama berbasis satu horizon.
def calculate_actual_direction(
    df: pd.DataFrame,
    close_column: str = "Close",
    forward_periods: int = 1,
) -> pd.DataFrame:
    """Add actual future price direction from a single forward return."""
    metric_df = calculate_forward_return(
        df,
        close_column=close_column,
        forward_periods=forward_periods,
    )
    metric_df[ACTUAL_DIRECTION_COLUMN] = "UNKNOWN"
    metric_df.loc[metric_df[FORWARD_RETURN_COLUMN] > 0, ACTUAL_DIRECTION_COLUMN] = "UP"
    metric_df.loc[metric_df[FORWARD_RETURN_COLUMN] < 0, ACTUAL_DIRECTION_COLUMN] = "DOWN"
    metric_df.loc[metric_df[FORWARD_RETURN_COLUMN] == 0, ACTUAL_DIRECTION_COLUMN] = "FLAT"
    return metric_df


# CATATAN FUNGSI: Menentukan arah harga aktual berdasarkan Average Forward Return.
# CARA KERJA SINGKAT: Average Forward Return positif diberi label UP, negatif DOWN, nol FLAT, dan data tidak tersedia UNKNOWN.
# KEGUNAAN: Dipakai untuk menilai apakah sinyal BUY/SELL sesuai arah harga rata-rata ke depan.
def calculate_average_actual_direction(
    df: pd.DataFrame,
    close_column: str = "Close",
    forward_horizons: list[int] | tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """Add actual direction based on average forward return."""
    metric_df = calculate_average_forward_return(
        df,
        close_column=close_column,
        forward_horizons=forward_horizons,
    )

    metric_df[ACTUAL_DIRECTION_COLUMN] = "UNKNOWN"
    metric_df.loc[
        metric_df[AVERAGE_FORWARD_RETURN_COLUMN] > 0,
        ACTUAL_DIRECTION_COLUMN,
    ] = "UP"
    metric_df.loc[
        metric_df[AVERAGE_FORWARD_RETURN_COLUMN] < 0,
        ACTUAL_DIRECTION_COLUMN,
    ] = "DOWN"
    metric_df.loc[
        metric_df[AVERAGE_FORWARD_RETURN_COLUMN] == 0,
        ACTUAL_DIRECTION_COLUMN,
    ] = "FLAT"

    return metric_df


# CATATAN FUNGSI: Mengevaluasi akurasi sinyal BUY/SELL pada satu horizon.
# CARA KERJA SINGKAT: Fungsi menghitung arah aktual lalu meneruskan penilaian ke evaluator umum.
# KEGUNAAN: Dipertahankan agar kode lama yang memakai single horizon tetap dapat berjalan.
def evaluate_signal_performance(
    df: pd.DataFrame,
    signal_column: str,
    forward_periods: int = 1,
) -> dict[str, float | int | str]:
    """
    Evaluate BUY and SELL signal accuracy against one future price direction.

    This function is kept for compatibility with older single-horizon evaluation.
    """
    metric_df = calculate_actual_direction(df, forward_periods=forward_periods)
    return _evaluate_from_direction(metric_df, signal_column)


# CATATAN FUNGSI: Mengevaluasi akurasi sinyal BUY/SELL menggunakan Average Forward Return.
# CARA KERJA SINGKAT: Fungsi membentuk arah aktual dari rata-rata return T+1, T+3, T+5, dan T+10, lalu menghitung total aktif, benar, DA, dan Hit Rate.
# KEGUNAAN: Dipakai sebagai evaluator utama dalam WFA penelitian.
def evaluate_signal_performance_average_forward(
    df: pd.DataFrame,
    signal_column: str,
    forward_horizons: list[int] | tuple[int, ...] | None = None,
) -> dict[str, float | int | str]:
    """
    Evaluate BUY and SELL signal accuracy using average forward return.

    BUY is correct when average forward return is positive.
    SELL is correct when average forward return is negative.
    """
    horizons = _normalize_forward_horizons(forward_horizons)
    metric_df = calculate_average_actual_direction(
        df,
        forward_horizons=horizons,
    )
    result = _evaluate_from_direction(
        metric_df,
        signal_column,
        evaluable_column=AVERAGE_FORWARD_RETURN_COLUMN,
    )
    result["evaluation_method"] = "average_forward_return"
    result["forward_horizons"] = ",".join(str(horizon) for horizon in horizons)
    return result


# CATATAN FUNGSI: Mengembalikan nilai Directional Accuracy dari kolom sinyal tertentu.
# CARA KERJA SINGKAT: Fungsi memanggil evaluasi sinyal lalu mengambil field directional_accuracy.
# KEGUNAAN: Memudahkan pemanggilan metrik DA secara langsung.
def calculate_directional_accuracy(
    df: pd.DataFrame,
    signal_column: str,
    forward_periods: int = 1,
) -> float:
    """Return Directional Accuracy percentage for a signal column."""
    return float(
        evaluate_signal_performance(
            df,
            signal_column,
            forward_periods=forward_periods,
        )["directional_accuracy"]
    )


# CATATAN FUNGSI: Mengembalikan nilai Hit Rate dari kolom sinyal tertentu.
# CARA KERJA SINGKAT: Fungsi memanggil evaluasi sinyal lalu mengambil field hit_rate.
# KEGUNAAN: Memudahkan pemanggilan metrik Hit Rate secara langsung.
def calculate_hit_rate(
    df: pd.DataFrame,
    signal_column: str,
    forward_periods: int = 1,
) -> float:
    """Return Hit Rate percentage for a signal column."""
    return float(
        evaluate_signal_performance(
            df,
            signal_column,
            forward_periods=forward_periods,
        )["hit_rate"]
    )


# CATATAN FUNGSI: Mengevaluasi semua kolom sinyal yang tersedia pada data.
# CARA KERJA SINGKAT: Fungsi memeriksa kolom MA, MACD, dan RSI yang ada lalu mengevaluasinya satu per satu.
# KEGUNAAN: Dipakai untuk membandingkan beberapa indikator tanpa membentuk ulang sinyal.
def evaluate_all_signal_columns(
    df: pd.DataFrame,
    forward_periods: int = 1,
) -> list[dict[str, float | int | str]]:
    """Evaluate available signal columns without generating missing signals."""
    metric_df = _prepare_metric_dataframe(df)
    results = []

    for signal_column in SIGNAL_COLUMNS:
        if signal_column in metric_df.columns:
            results.append(
                evaluate_signal_performance(
                    metric_df,
                    signal_column,
                    forward_periods=forward_periods,
                )
            )

    return results


# CATATAN FUNGSI: Mengevaluasi semua kolom sinyal dengan Average Forward Return.
# CARA KERJA SINGKAT: Setiap kolom sinyal yang tersedia dinilai menggunakan horizon rata-rata yang sama.
# KEGUNAAN: Dipakai untuk evaluasi multi-indikator yang konsisten dengan metode final.
def evaluate_all_signal_columns_average_forward(
    df: pd.DataFrame,
    forward_horizons: list[int] | tuple[int, ...] | None = None,
) -> list[dict[str, float | int | str]]:
    """Evaluate available signal columns using average forward return."""
    metric_df = _prepare_metric_dataframe(df)
    results = []

    for signal_column in SIGNAL_COLUMNS:
        if signal_column in metric_df.columns:
            results.append(
                evaluate_signal_performance_average_forward(
                    metric_df,
                    signal_column,
                    forward_horizons=forward_horizons,
                )
            )

    return results


# CATATAN FUNGSI: Menghitung metrik dari data yang sudah memiliki arah aktual.
# CARA KERJA SINGKAT: Fungsi hanya mengambil baris evaluable, menyaring BUY/SELL, menghitung sinyal benar, DA, dan Hit Rate.
# KEGUNAAN: Menjadi inti evaluasi agar perhitungan metrik konsisten di seluruh service.
def _evaluate_from_direction(
    metric_df: pd.DataFrame,
    signal_column: str,
    evaluable_column: str = FORWARD_RETURN_COLUMN,
) -> dict[str, float | int | str]:
    """Evaluate active BUY/SELL rows from an already-built direction column."""
    _validate_column(metric_df, signal_column)
    _validate_column(metric_df, evaluable_column)

    evaluable_rows = metric_df[metric_df[evaluable_column].notna()]
    active_rows = evaluable_rows[evaluable_rows[signal_column].isin(ACTIVE_SIGNALS)]

    total_active_signals = int(len(active_rows))
    if total_active_signals == 0:
        return {
            "signal_column": signal_column,
            "total_active_signals": 0,
            "correct_signals": 0,
            "directional_accuracy": 0.0,
            "hit_rate": 0.0,
        }

    buy_correct = (active_rows[signal_column] == "BUY") & (
        active_rows[ACTUAL_DIRECTION_COLUMN] == "UP"
    )
    sell_correct = (active_rows[signal_column] == "SELL") & (
        active_rows[ACTUAL_DIRECTION_COLUMN] == "DOWN"
    )

    correct_signals = int((buy_correct | sell_correct).sum())
    score = (correct_signals / total_active_signals) * 100

    return {
        "signal_column": signal_column,
        "total_active_signals": total_active_signals,
        "correct_signals": correct_signals,
        "directional_accuracy": score,
        "hit_rate": score,
    }


# CATATAN FUNGSI: Menyiapkan DataFrame evaluasi agar berbasis index Date.
# CARA KERJA SINGKAT: Data disalin, kolom Date dijadikan index jika ada, lalu diurutkan kronologis.
# KEGUNAAN: Mencegah kesalahan evaluasi akibat urutan tanggal atau format index yang tidak seragam.
def _prepare_metric_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copied DataFrame sorted by date."""
    if df is None or df.empty:
        raise ValueError("Data evaluasi kosong.")

    metric_df = df.copy()

    if "Date" in metric_df.columns:
        metric_df["Date"] = pd.to_datetime(metric_df["Date"])
        metric_df = metric_df.set_index("Date")

    if not isinstance(metric_df.index, pd.DatetimeIndex):
        metric_df.index = pd.to_datetime(metric_df.index)

    metric_df.index.name = "Date"
    return metric_df.sort_index()


# CATATAN FUNGSI: Memastikan kolom yang dibutuhkan tersedia.
# CARA KERJA SINGKAT: Jika kolom tidak ada, fungsi menghentikan proses dengan ValueError.
# KEGUNAAN: Mencegah perhitungan berjalan dengan data yang tidak lengkap.
def _validate_column(df: pd.DataFrame, column: str) -> None:
    """Ensure a required column is available."""
    if column not in df.columns:
        raise ValueError(f"Kolom tidak ditemukan: {column}")


# CATATAN FUNGSI: Memastikan horizon evaluasi bernilai positif.
# CARA KERJA SINGKAT: Nilai forward_periods dikonversi ke integer dan harus minimal 1.
# KEGUNAAN: Mencegah horizon yang tidak logis seperti 0 atau negatif.
def _validate_forward_periods(forward_periods: int) -> None:
    """Ensure the evaluation horizon is a positive row count."""
    if int(forward_periods) < 1:
        raise ValueError("forward_periods harus lebih besar atau sama dengan 1.")


# CATATAN FUNGSI: Menormalkan daftar horizon evaluasi.
# CARA KERJA SINGKAT: Fungsi mengambil default jika kosong, menghapus duplikasi, mengurutkan, dan memvalidasi setiap horizon.
# KEGUNAAN: Menjamin evaluasi T+1, T+3, T+5, dan T+10 dipakai secara konsisten.
def _normalize_forward_horizons(
    forward_horizons: list[int] | tuple[int, ...] | None,
) -> list[int]:
    """Return sorted unique positive forward horizons."""
    horizons = DEFAULT_FORWARD_HORIZONS if forward_horizons is None else list(forward_horizons)
    normalized = sorted({int(horizon) for horizon in horizons})

    if not normalized:
        raise ValueError("forward_horizons tidak boleh kosong.")

    for horizon in normalized:
        _validate_forward_periods(horizon)

    return normalized