from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.data_service import END_DATE, REQUIRED_OHLCV_COLUMNS, START_DATE, load_or_fetch_price_data, validate_ohlcv
from services.mapping_service import load_mapping

DATA_DIR = PROJECT_ROOT / "data"

ALL_OHLCV_PATH = DATA_DIR / "all_stock_ohlcv.csv"
SUMMARY_PATH = DATA_DIR / "all_stock_ohlcv_summary.csv"
BY_STOCK_XLSX_PATH = DATA_DIR / "ohclv_by_stock.xlsx"
BY_SECTOR_XLSX_PATH = DATA_DIR / "ohclv_by_sector.xlsx"

OUTPUT_COLUMNS = [
    "Date",
    "ticker",
    "ticker_yfinance",
    "sektor",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]


def _safe_string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_sample_mapping() -> pd.DataFrame:
    mapping_df = load_mapping()

    sample_df = mapping_df[
        mapping_df["status_data"].astype(str).str.strip().str.casefold().eq("lengkap")
        & mapping_df["is_sample"].astype(str).str.strip().str.casefold().eq("ya")
    ].copy()

    sample_df = sample_df.sort_values(["sektor", "ticker"]).reset_index(drop=True)

    if sample_df.empty:
        raise ValueError("Tidak ada saham sampel lengkap pada mapping.")

    return sample_df


def build_one_stock(row: pd.Series) -> tuple[pd.DataFrame, dict[str, Any]]:
    ticker = _safe_string(row.get("ticker"))
    ticker_yfinance = _safe_string(row.get("ticker_yfinance"))
    sector = _safe_string(row.get("sektor"))

    price_df = load_or_fetch_price_data(
        ticker_yfinance,
        start_date=START_DATE,
        end_date=END_DATE,
        use_cache=True,
    )

    validate_ohlcv(price_df)

    df = price_df.dropna(subset=REQUIRED_OHLCV_COLUMNS).copy()
    df = df.reset_index()

    if "Date" not in df.columns:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "Date"})

    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df["ticker"] = ticker
    df["ticker_yfinance"] = ticker_yfinance
    df["sektor"] = sector

    df = df[OUTPUT_COLUMNS].copy()

    summary = {
        "ticker": ticker,
        "ticker_yfinance": ticker_yfinance,
        "sektor": sector,
        "jumlah_data": int(len(df)),
        "tanggal_awal": df["Date"].min() if not df.empty else "",
        "tanggal_akhir": df["Date"].max() if not df.empty else "",
        "open_missing": int(df["Open"].isna().sum()),
        "high_missing": int(df["High"].isna().sum()),
        "low_missing": int(df["Low"].isna().sum()),
        "close_missing": int(df["Close"].isna().sum()),
        "volume_missing": int(df["Volume"].isna().sum()),
    }

    return df, summary


def export_by_stock(all_df: pd.DataFrame) -> None:
    with pd.ExcelWriter(BY_STOCK_XLSX_PATH, engine="openpyxl") as writer:
        for ticker, group in all_df.groupby("ticker", sort=True):
            sheet_name = str(ticker)[:31]
            group.to_excel(writer, sheet_name=sheet_name, index=False)


def export_by_sector(all_df: pd.DataFrame) -> None:
    with pd.ExcelWriter(BY_SECTOR_XLSX_PATH, engine="openpyxl") as writer:
        for sector, group in all_df.groupby("sektor", sort=True):
            sheet_name = str(sector)[:31]
            group.to_excel(writer, sheet_name=sheet_name, index=False)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    sample_df = load_sample_mapping()

    print(f"Periode data: {START_DATE} sampai {END_DATE} exclusive")
    print(f"Jumlah saham sampel: {len(sample_df)}")
    print("Membangun dataset gabungan OHLCV...\n")

    frames: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []

    for index, row in sample_df.iterrows():
        ticker = _safe_string(row.get("ticker"))
        ticker_yfinance = _safe_string(row.get("ticker_yfinance"))

        print(f"[{index + 1}/{len(sample_df)}] {ticker} ({ticker_yfinance}) ... ", end="")

        try:
            stock_df, summary = build_one_stock(row)
            frames.append(stock_df)
            summaries.append(summary)
            print(f"OK, {summary['jumlah_data']} rows, {summary['tanggal_awal']} s.d. {summary['tanggal_akhir']}")
        except Exception as exc:
            summaries.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sektor": _safe_string(row.get("sektor")),
                    "jumlah_data": 0,
                    "tanggal_awal": "",
                    "tanggal_akhir": "",
                    "open_missing": None,
                    "high_missing": None,
                    "low_missing": None,
                    "close_missing": None,
                    "volume_missing": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"ERROR: {exc}")

    if not frames:
        raise RuntimeError("Tidak ada data OHLCV yang berhasil digabungkan.")

    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.sort_values(["sektor", "ticker", "Date"]).reset_index(drop=True)

    summary_df = pd.DataFrame(summaries)

    all_df.to_csv(ALL_OHLCV_PATH, index=False)
    summary_df.to_csv(SUMMARY_PATH, index=False)

    export_by_stock(all_df)
    export_by_sector(all_df)

    print("\nDataset gabungan selesai.")
    print(f"All OHLCV       : {ALL_OHLCV_PATH}")
    print(f"Summary         : {SUMMARY_PATH}")
    print(f"By stock Excel  : {BY_STOCK_XLSX_PATH}")
    print(f"By sector Excel : {BY_SECTOR_XLSX_PATH}")

    print("\nRingkasan tanggal akhir:")
    print(summary_df["tanggal_akhir"].value_counts(dropna=False).to_string())

    print("\nRingkasan jumlah data:")
    print(summary_df["jumlah_data"].describe().to_string())

    failed = summary_df[summary_df.get("jumlah_data", 0).eq(0)]
    if not failed.empty:
        print("\nData gagal:")
        print(failed[["ticker", "ticker_yfinance", "sektor", "error"]].to_string(index=False))


if __name__ == "__main__":
    main()