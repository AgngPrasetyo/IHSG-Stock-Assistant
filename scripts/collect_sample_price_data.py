"""Collect and cache OHLCV price data for sample stocks from the mapping file."""

# CATATAN FILE:
# File ini berisi script pengambilan dan caching data harga OHLCV untuk saham sampel.
# Kegunaannya adalah memastikan data harga tersedia, tervalidasi, dan memiliki laporan status pengambilan data.


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
    LATEST_DATA_END_DATE,
    REQUIRED_OHLCV_COLUMNS,
    START_DATE,
    load_or_fetch_price_data,
    validate_ohlcv,
)
from services.mapping_service import load_mapping  # noqa: E402


REPORT_COLUMNS = [
    "ticker",
    "ticker_yfinance",
    "sektor",
    "status_fetch",
    "jumlah_data",
    "tanggal_awal",
    "tanggal_akhir",
    "kolom_ohlcv_lengkap",
    "error_message",
]

REPORT_PATH = PROJECT_ROOT / "data" / f"price_fetch_report_{START_DATE}_{LATEST_DATA_END_DATE}.csv"


# CATATAN FUNGSI: Menyaring saham yang akan diambil datanya.
# CARA KERJA SINGKAT: Mapping difilter berdasarkan status lengkap, sampel penelitian, sektor opsional, dan limit opsional.
# KEGUNAAN: Dipakai untuk membatasi proses fetch sesuai kebutuhan.
def filter_sample_stocks(
    mapping_df: pd.DataFrame,
    sector: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Filter mapping rows to complete sample stocks, optionally by sector and limit."""
    filtered_df = mapping_df.copy()
    filtered_df = filtered_df[
        filtered_df["status_data"].astype(str).str.strip().str.lower() == "lengkap"
    ]

    if "is_sample" in filtered_df.columns:
        sample_mask = filtered_df["is_sample"].astype(str).str.strip().str.lower() == "ya"
        filtered_df = filtered_df[sample_mask]

    if sector:
        filtered_df = filtered_df[
            filtered_df["sektor"].astype(str).str.strip().str.lower()
            == str(sector).strip().lower()
        ]

    if limit is not None:
        filtered_df = filtered_df.head(limit)

    return filtered_df.reset_index(drop=True)


# CATATAN FUNGSI: Mengambil atau memuat cache harga untuk saham sampel.
# CARA KERJA SINGKAT: Setiap saham diproses, hasil sukses/gagal dicatat, lalu laporan disimpan.
# KEGUNAAN: Dipakai untuk validasi ketersediaan data harga.
def collect_sample_price_data(
    refresh: bool = False,
    limit: int | None = None,
    sector: str | None = None,
    report_path: str | Path = REPORT_PATH,
) -> pd.DataFrame:
    """Fetch/cache price data for filtered sample stocks and write a CSV report."""
    mapping_df = load_mapping()
    sample_df = filter_sample_stocks(mapping_df, sector=sector, limit=limit)
    total = len(sample_df)
    report_rows = []

    for row_number, (_, row) in enumerate(sample_df.iterrows(), start=1):
        ticker = _safe_string(row.get("ticker"))
        ticker_yfinance = _safe_string(row.get("ticker_yfinance"))
        print(f"[{row_number}/{total}] Fetching {ticker_yfinance} ... ", end="")

        report_row = _fetch_one_stock_report(
            ticker=ticker,
            ticker_yfinance=ticker_yfinance,
            sector=_safe_string(row.get("sektor")),
            refresh=refresh,
        )
        report_rows.append(report_row)

        if report_row["status_fetch"] == "SUCCESS":
            print(f"SUCCESS, {report_row['jumlah_data']} rows")
        else:
            print(f"FAILED, {report_row['error_message']}")

    report_df = pd.DataFrame(report_rows, columns=REPORT_COLUMNS)
    save_report(report_df, report_path)
    return report_df


# CATATAN FUNGSI: Menyimpan laporan pengambilan data harga.
# CARA KERJA SINGKAT: Folder dibuat jika belum ada lalu DataFrame ditulis ke CSV.
# KEGUNAAN: Menyediakan bukti status fetch data.
def save_report(report_df: pd.DataFrame, report_path: str | Path = REPORT_PATH) -> Path:
    """Save the collection report as CSV."""
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(path, index=False)
    return path


# CATATAN FUNGSI: Membaca argumen command-line untuk script.
# CARA KERJA SINGKAT: Argumen refresh, limit, dan sector didefinisikan melalui argparse.
# KEGUNAAN: Memudahkan menjalankan script dengan variasi kebutuhan.
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the cache builder."""
    parser = argparse.ArgumentParser(
        description="Collect and cache OHLCV data for sample stocks."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch data again from Yahoo Finance instead of using existing cache.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of sample stocks fetched.",
    )
    parser.add_argument(
        "--sector",
        type=str,
        default=None,
        help="Fetch only sample stocks from a specific sector.",
    )
    return parser.parse_args()


# CATATAN FUNGSI: Menjalankan script pengumpulan data harga.
# CARA KERJA SINGKAT: Argumen dibaca, data dikumpulkan, laporan dicetak, dan tanggal akhir divalidasi.
# KEGUNAAN: Dipakai sebagai entry point script cache harga.
def main() -> None:
    """CLI entry point."""
    args = parse_args()
    report_df = collect_sample_price_data(
        refresh=args.refresh,
        limit=args.limit,
        sector=args.sector,
    )
    print(f"Report saved to {REPORT_PATH}")
    print(f"SUCCESS: {(report_df['status_fetch'] == 'SUCCESS').sum()}")
    print(f"FAILED: {(report_df['status_fetch'] == 'FAILED').sum()}")
    last_dates = set(report_df.loc[report_df["status_fetch"] == "SUCCESS", "tanggal_akhir"])
    if last_dates == {"2026-06-26"}:
        print("Validasi tanggal akhir: seluruh saham tersedia sampai 2026-06-26.")
    elif last_dates == {"2026-06-25"}:
        print("Data 2026-06-26 kemungkinan belum tersedia di yfinance; jalankan ulang fetch nanti.")
    else:
        print(f"Validasi tanggal akhir perlu ditinjau: {sorted(last_dates)}")


# CATATAN FUNGSI: Mengambil data satu saham dan membentuk baris laporan.
# CARA KERJA SINGKAT: Data harga dimuat/fetch, divalidasi, lalu status, jumlah data, dan tanggal dicatat.
# KEGUNAAN: Dipakai oleh collect_sample_price_data untuk setiap saham.
def _fetch_one_stock_report(
    ticker: str,
    ticker_yfinance: str,
    sector: str,
    refresh: bool,
) -> dict[str, Any]:
    """Fetch one stock and return a report row."""
    base_row = {
        "ticker": ticker,
        "ticker_yfinance": ticker_yfinance,
        "sektor": sector,
        "status_fetch": "FAILED",
        "jumlah_data": 0,
        "tanggal_awal": "",
        "tanggal_akhir": "",
        "kolom_ohlcv_lengkap": False,
        "error_message": "",
    }

    try:
        price_df = load_or_fetch_price_data(
            ticker_yfinance,
            start_date=START_DATE,
            end_date=LATEST_DATA_END_DATE,
            use_cache=not refresh,
        )
        validate_ohlcv(price_df)
        ohlcv_complete = all(column in price_df.columns for column in REQUIRED_OHLCV_COLUMNS)

        return {
            **base_row,
            "status_fetch": "SUCCESS",
            "jumlah_data": int(len(price_df)),
            "tanggal_awal": _format_date(price_df.index.min()),
            "tanggal_akhir": _format_date(price_df.index.max()),
            "kolom_ohlcv_lengkap": bool(ohlcv_complete),
            "error_message": "",
        }
    except Exception as exc:
        return {
            **base_row,
            "status_fetch": "FAILED",
            "error_message": str(exc),
        }


# CATATAN FUNGSI: Mengubah tanggal/index menjadi format YYYY-MM-DD.
# CARA KERJA SINGKAT: Nilai kosong menjadi string kosong, nilai valid dikonversi ke tanggal ISO.
# KEGUNAAN: Dipakai dalam laporan fetch harga.
def _format_date(value: Any) -> str:
    """Format index/date values for CSV report output."""
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


# CATATAN FUNGSI: Mengubah nilai nullable menjadi string aman.
# CARA KERJA SINGKAT: NaN menjadi kosong dan nilai lain di-strip.
# KEGUNAAN: Dipakai saat membaca ticker, sektor, dan metadata mapping.
def _safe_string(value: Any) -> str:
    """Convert nullable mapping values to safe strings."""
    if pd.isna(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    main()


