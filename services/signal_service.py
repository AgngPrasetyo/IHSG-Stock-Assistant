"""Technical-analysis signals for final SMA10/SMA50, MACD, and RSI methods."""
# ================================================================
# CATATAN FILE:
# File ini bertugas membentuk sinyal teknikal final BUY, SELL, atau HOLD berdasarkan aturan MA Crossover, MACD, dan RSI. File ini menggunakan nilai indikator yang sudah dihitung sebelumnya.
# Catatan ini ditambahkan untuk membantu penjelasan kode saat sidang.
# Bagian di bawah ini tidak mengubah logika program; hanya berupa komentar dokumentasi.
# ================================================================


from __future__ import annotations

import pandas as pd

from services.indicator_service import calculate_macd, calculate_rsi, calculate_sma

BUY, SELL, HOLD = "BUY", "SELL", "HOLD"
MA_CROSSOVER_SIGNAL_COLUMN = "MA_Crossover_Signal"
MA_SIGNAL_COLUMN = MA_CROSSOVER_SIGNAL_COLUMN  # Compatibility alias for old imports.
MACD_TRADE_SIGNAL_COLUMN = "MACD_Trade_Signal"
RSI_SIGNAL_COLUMN = "RSI_Signal"



# CATATAN FUNGSI: Membentuk sinyal MA Crossover berdasarkan perpotongan SMA10 dan SMA50.
# CARA KERJA SINGKAT: BUY muncul ketika SMA10 memotong SMA50 dari bawah ke atas; SELL muncul ketika SMA10 memotong dari atas ke bawah; selain itu HOLD.
# KEGUNAAN: Menentukan sinyal teknikal final untuk indikator MA Crossover.
def generate_ma_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Signal MA Crossover SMA10/SMA50 without additional filters."""
    signal_df = _ensure_sma_columns(_prepare_signal_dataframe(df), 10, 50)

    signal_df[MA_CROSSOVER_SIGNAL_COLUMN] = HOLD

    valid = _has_current_and_previous_values(signal_df, ["SMA10", "SMA50"])

    bullish_cross = (
        valid
        & (signal_df["SMA10"].shift(1) <= signal_df["SMA50"].shift(1))
        & (signal_df["SMA10"] > signal_df["SMA50"])
    )

    bearish_cross = (
        valid
        & (signal_df["SMA10"].shift(1) >= signal_df["SMA50"].shift(1))
        & (signal_df["SMA10"] < signal_df["SMA50"])
    )

    signal_df.loc[bullish_cross, MA_CROSSOVER_SIGNAL_COLUMN] = BUY
    signal_df.loc[bearish_cross, MA_CROSSOVER_SIGNAL_COLUMN] = SELL

    return signal_df



# CATATAN FUNGSI: Membentuk sinyal MACD berdasarkan crossover MACD Line dan Signal Line.
# CARA KERJA SINGKAT: BUY muncul saat MACD Line memotong Signal Line ke atas; SELL muncul saat memotong ke bawah; selain itu HOLD.
# KEGUNAAN: Menentukan sinyal teknikal final untuk indikator MACD.
def generate_macd_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Signal MACD Line crossover against Signal Line without additional filters."""
    signal_df = _prepare_signal_dataframe(df)

    if not {"MACD", "MACD_Signal"}.issubset(signal_df.columns):
        signal_df = calculate_macd(signal_df)

    signal_df[MACD_TRADE_SIGNAL_COLUMN] = HOLD

    valid = _has_current_and_previous_values(signal_df, ["MACD", "MACD_Signal"])

    bullish_cross = (
        valid
        & (signal_df["MACD"].shift(1) <= signal_df["MACD_Signal"].shift(1))
        & (signal_df["MACD"] > signal_df["MACD_Signal"])
    )

    bearish_cross = (
        valid
        & (signal_df["MACD"].shift(1) >= signal_df["MACD_Signal"].shift(1))
        & (signal_df["MACD"] < signal_df["MACD_Signal"])
    )

    signal_df.loc[bullish_cross, MACD_TRADE_SIGNAL_COLUMN] = BUY
    signal_df.loc[bearish_cross, MACD_TRADE_SIGNAL_COLUMN] = SELL

    return signal_df



# CATATAN FUNGSI: Membentuk sinyal RSI berdasarkan keluarnya RSI dari area ekstrem.
# CARA KERJA SINGKAT: BUY muncul saat RSI naik keluar dari oversold; SELL muncul saat RSI turun keluar dari overbought; selain itu HOLD.
# KEGUNAAN: Menentukan sinyal teknikal final untuk indikator RSI.
def generate_rsi_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Signal RSI exits from oversold/overbought areas without additional filters."""
    signal_df = _prepare_signal_dataframe(df)

    if "RSI" not in signal_df.columns:
        signal_df = calculate_rsi(signal_df, 14)

    signal_df[RSI_SIGNAL_COLUMN] = HOLD

    valid = _has_current_and_previous_values(signal_df, ["RSI"])

    buy = (
        valid
        & (signal_df["RSI"].shift(1) < 30)
        & (signal_df["RSI"] >= 30)
    )

    sell = (
        valid
        & (signal_df["RSI"].shift(1) > 70)
        & (signal_df["RSI"] <= 70)
    )

    signal_df.loc[buy, RSI_SIGNAL_COLUMN] = BUY
    signal_df.loc[sell, RSI_SIGNAL_COLUMN] = SELL

    return signal_df



# CATATAN FUNGSI: Membentuk sinyal teknikal BUY, SELL, atau HOLD berdasarkan aturan indikator final.
# CARA KERJA SINGKAT: Memastikan kolom indikator tersedia, membandingkan nilai saat ini dan nilai sebelumnya, lalu menandai kondisi crossover atau keluar area ekstrem.
# KEGUNAAN: Menghasilkan kolom sinyal yang digunakan untuk dashboard, sinyal terbaru, dan evaluasi performa.
def generate_all_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate final MA Crossover, MACD, and RSI signal columns.
    """
    signal_df = _ensure_sma_columns(_prepare_signal_dataframe(df), 10, 50)
    signal_df = calculate_macd(signal_df)
    signal_df = calculate_rsi(signal_df, 14)
    signal_df = generate_ma_signal(signal_df)
    signal_df = generate_macd_signal(signal_df)
    return generate_rsi_signal(signal_df)



# CATATAN FUNGSI: Mengambil informasi yang dibutuhkan terkait latest signal.
# CARA KERJA SINGKAT: Membaca sumber data yang relevan, mencari baris atau kolom yang sesuai, lalu mengembalikan nilai terpilih.
# KEGUNAAN: Menyediakan informasi pendukung untuk proses analisis, sinyal, mapping, atau laporan.
def get_latest_signal(df: pd.DataFrame, indicator_name: str) -> dict[str, str]:
    """Return the latest final-method signal and deterministic reason."""
    signal_df = _ensure_indicator_signal(df, indicator_name)
    column = _get_signal_column(indicator_name)
    row = signal_df.iloc[-1]
    return {
    "indicator": _normalize_indicator_name(indicator_name),
    "signal": row[column],
    "date": signal_df.index[-1].strftime("%Y-%m-%d"),
    "reason": _build_reason(row, indicator_name),
}



# CATATAN FUNGSI: Menjalankan proses  prepare signal dataframe sesuai kebutuhan modul ini.
# CARA KERJA SINGKAT: Memproses input yang diterima, melakukan validasi seperlunya, lalu mengembalikan hasil yang siap digunakan tahap berikutnya.
# KEGUNAAN: Mendukung alur sistem agar data atau hasil analisis tetap terstruktur dan konsisten.
def _prepare_signal_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("Data indikator kosong.")
    signal_df = df.copy()
    if "Date" in signal_df.columns:
        signal_df["Date"] = pd.to_datetime(signal_df["Date"])
        signal_df = signal_df.set_index("Date")
    if not isinstance(signal_df.index, pd.DatetimeIndex):
        signal_df.index = pd.to_datetime(signal_df.index)
    signal_df.index.name = "Date"
    return signal_df.sort_index()



# CATATAN FUNGSI: Menjalankan proses  ensure sma columns sesuai kebutuhan modul ini.
# CARA KERJA SINGKAT: Memproses input yang diterima, melakukan validasi seperlunya, lalu mengembalikan hasil yang siap digunakan tahap berikutnya.
# KEGUNAAN: Mendukung alur sistem agar data atau hasil analisis tetap terstruktur dan konsisten.
def _ensure_sma_columns(df: pd.DataFrame, *windows: int) -> pd.DataFrame:
    signal_df = df.copy()
    for window in windows:
        column = f"SMA{window}"
        if column not in signal_df.columns:
            signal_df[column] = calculate_sma(signal_df, window)
    return signal_df




# CATATAN FUNGSI: Menjalankan proses  has current and previous values sesuai kebutuhan modul ini.
# CARA KERJA SINGKAT: Memproses input yang diterima, melakukan validasi seperlunya, lalu mengembalikan hasil yang siap digunakan tahap berikutnya.
# KEGUNAAN: Mendukung alur sistem agar data atau hasil analisis tetap terstruktur dan konsisten.
def _has_current_and_previous_values(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    return df[columns].notna().all(axis=1) & df[columns].shift(1).notna().all(axis=1)



# CATATAN FUNGSI: Menjalankan proses  ensure indicator signal sesuai kebutuhan modul ini.
# CARA KERJA SINGKAT: Memproses input yang diterima, melakukan validasi seperlunya, lalu mengembalikan hasil yang siap digunakan tahap berikutnya.
# KEGUNAAN: Mendukung alur sistem agar data atau hasil analisis tetap terstruktur dan konsisten.
def _ensure_indicator_signal(df: pd.DataFrame, indicator_name: str) -> pd.DataFrame:
    name = _normalize_indicator_name(indicator_name)
    if name == "MA Crossover":
        return generate_ma_signal(df)
    if name == "MACD":
        return generate_macd_signal(df)
    return generate_rsi_signal(df)



# CATATAN FUNGSI: Mengambil informasi yang dibutuhkan terkait  signal column.
# CARA KERJA SINGKAT: Membaca sumber data yang relevan, mencari baris atau kolom yang sesuai, lalu mengembalikan nilai terpilih.
# KEGUNAAN: Menyediakan informasi pendukung untuk proses analisis, sinyal, mapping, atau laporan.
def _get_signal_column(indicator_name: str) -> str:
    return {"MA Crossover": MA_CROSSOVER_SIGNAL_COLUMN, "MACD": MACD_TRADE_SIGNAL_COLUMN, "RSI": RSI_SIGNAL_COLUMN}[_normalize_indicator_name(indicator_name)]



# CATATAN FUNGSI: Menormalkan teks, nama indikator, ticker, atau data agar formatnya konsisten.
# CARA KERJA SINGKAT: Membersihkan karakter, menyamakan kapitalisasi, mengatur indeks tanggal, atau mengganti variasi istilah ke format baku.
# KEGUNAAN: Mengurangi kesalahan pencocokan dan menjaga hasil sistem tetap stabil.
def _normalize_indicator_name(indicator_name: str) -> str:
    name = str(indicator_name).strip().lower()
    if name in {
        "ma crossover",
        "moving average crossover",
        "sma crossover",
        "sma10/sma50",
    }:
        return "MA Crossover"
    if name == "macd":
        return "MACD"
    if name == "rsi":
        return "RSI"
    raise ValueError("indicator_name harus berupa MA Crossover, MACD, atau RSI.")



# CATATAN FUNGSI: Menjalankan proses  build reason sesuai kebutuhan modul ini.
# CARA KERJA SINGKAT: Memproses input yang diterima, melakukan validasi seperlunya, lalu mengembalikan hasil yang siap digunakan tahap berikutnya.
# KEGUNAAN: Mendukung alur sistem agar data atau hasil analisis tetap terstruktur dan konsisten.
def _build_reason(row: pd.Series, indicator_name: str) -> str:
    name = _normalize_indicator_name(indicator_name)

    required = {
        "MA Crossover": ["Close", "SMA10", "SMA50"],
        "MACD": ["Close", "MACD", "MACD_Signal"],
        "RSI": ["Close", "RSI"],
    }[name]
    if any(pd.isna(row.get(column)) for column in required):
        return f"Nilai {name} belum cukup, sehingga sinyal analisis teknikal HOLD."

    descriptions = {
        "MA Crossover": "MA Crossover SMA10/SMA50 tanpa filter tambahan",
        "MACD": "MACD Line crossover terhadap Signal Line tanpa filter tambahan",
        "RSI": "RSI14 exit dari area ekstrem 30/70 tanpa filter tambahan",
    }

    return f"Sinyal {name} menggunakan {descriptions[name]}."