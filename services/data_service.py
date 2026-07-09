"""Data access utilities for historical OHLCV prices from Yahoo Finance."""

from __future__ import annotations

import contextlib
import io
import re
import tempfile
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


WARMUP_START_DATE = "2024-07-01"
START_DATE = "2024-10-21"
END_DATE = "2026-06-12"
LAST_EVALUATION_DATE = "2026-06-11"
WARMUP_TRADING_DAYS = 50
REQUIRED_OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "cache" / "prices"
YFINANCE_CACHE_DIR = PROJECT_ROOT / "cache" / "yfinance"

DATA_UNAVAILABLE_MESSAGE = (
    "Data historis saham belum tersedia secara lengkap pada periode penelitian yang digunakan. "
    "Silakan periksa kembali kode saham atau pilih saham lain yang tersedia dalam daftar sistem."
)


def _run_quietly(callback):
    """Run noisy third-party data calls without printing raw provider logs."""
    output_buffer = io.StringIO()
    error_buffer = io.StringIO()

    with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(error_buffer):
        return callback()
    

    
def fetch_price_data(ticker_yfinance: str,start_date: str = START_DATE,end_date: str = END_DATE,) -> pd.DataFrame:
    
    """
    Mengambil data OHLCV harian dari Yahoo Finance dengan beberapa fallback.

    Urutan pengambilan data adalah yf.download, Ticker.history, lalu endpoint chart Yahoo.
    Jika seluruh sumber gagal atau kosong, fungsi melempar pesan ketersediaan data yang
    aman untuk ditampilkan kepada pengguna.
    """

    if not ticker_yfinance:
        raise ValueError("ticker_yfinance wajib diisi.")

    _configure_yfinance_cache()

    try:
        price_df = _run_quietly(lambda: yf.download(
            ticker_yfinance,
            start=start_date,
            end=end_date,
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        ))
    except Exception:
        price_df = pd.DataFrame()

    price_df = _normalize_price_dataframe(price_df)
    if price_df.empty:
        try:
           price_df = _run_quietly(lambda: yf.Ticker(ticker_yfinance).history(
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=False,
            ))
        except Exception:
            price_df = pd.DataFrame()

        price_df = _normalize_price_dataframe(price_df)

    if price_df.empty:
        price_df = _fetch_price_data_from_yahoo_chart(ticker_yfinance, start_date, end_date)
        price_df = _normalize_price_dataframe(price_df)

    if price_df.empty:
        raise ValueError(DATA_UNAVAILABLE_MESSAGE)

    validate_ohlcv(price_df)
    return price_df


def validate_ohlcv(df: pd.DataFrame) -> bool:
    """Validate that a DataFrame contains usable OHLCV data."""
    if df is None or df.empty:
        raise ValueError("Data OHLCV kosong.")

    missing_columns = [column for column in REQUIRED_OHLCV_COLUMNS if column not in df.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Kolom OHLCV wajib tidak lengkap: {missing}")

    if df["Close"].isna().all():
        raise ValueError("Kolom Close tidak memiliki nilai yang valid.")

    if df["Volume"].isna().all():
        raise ValueError("Kolom Volume tidak memiliki nilai yang valid.")

    return True


def get_cache_path(
    ticker_yfinance: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Path:
    """Build the CSV cache path for a ticker and date range."""
    if not ticker_yfinance:
        raise ValueError("ticker_yfinance wajib diisi.")

    safe_ticker = re.sub(r"[^A-Za-z0-9]+", "_", ticker_yfinance).strip("_").upper()
    filename = f"{safe_ticker}_{start_date}_{end_date}.csv"
    return CACHE_DIR / filename


def load_cached_price_data(
    ticker_yfinance: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> pd.DataFrame | None:
    """Load cached price data when available, otherwise return None."""
    cache_path = get_cache_path(ticker_yfinance, start_date, end_date)
    if not cache_path.exists():
        return None

    price_df = pd.read_csv(cache_path, parse_dates=["Date"])
    price_df = price_df.set_index("Date")
    price_df.index = pd.DatetimeIndex(price_df.index)
    return _normalize_price_dataframe(price_df)


def save_price_cache(
    ticker_yfinance: str,
    df: pd.DataFrame,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Path:
    """Save validated OHLCV data into the price cache as CSV."""
    validate_ohlcv(df)
    cache_path = get_cache_path(ticker_yfinance, start_date, end_date)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    price_df = _normalize_price_dataframe(df)
    price_df.to_csv(cache_path, index_label="Date")
    return cache_path


def load_or_fetch_price_data(
    ticker_yfinance: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Load price data from cache, or fetch from yfinance and cache the result."""
    if use_cache:
        cached_df = load_cached_price_data(ticker_yfinance, start_date, end_date)
        if cached_df is not None:
            validate_ohlcv(cached_df)
            return cached_df

    price_df = fetch_price_data(ticker_yfinance, start_date, end_date)
    validate_ohlcv(price_df)
    save_price_cache(ticker_yfinance, price_df, start_date, end_date)
    return price_df


def _normalize_price_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance/cache output into a Date-indexed OHLCV DataFrame."""
    if df is None:
        return pd.DataFrame()

    price_df = df.copy()

    if isinstance(price_df.columns, pd.MultiIndex):
        price_df.columns = [column[0] for column in price_df.columns]

    if "Date" in price_df.columns:
        price_df["Date"] = pd.to_datetime(price_df["Date"])
        price_df = price_df.set_index("Date")

    if not isinstance(price_df.index, pd.DatetimeIndex):
        price_df.index = pd.to_datetime(price_df.index)

    price_df.index.name = "Date"
    price_df = price_df.sort_index()
    return price_df


def _configure_yfinance_cache() -> None:
    """Point yfinance's internal cache to a project folder that is writable."""
    cache_dir = YFINANCE_CACHE_DIR
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        cache_dir = Path(tempfile.gettempdir()) / "stock_decision_assistant" / "yfinance"
        cache_dir.mkdir(parents=True, exist_ok=True)

    yf.set_tz_cache_location(str(cache_dir))


def _fetch_price_data_from_yahoo_chart(
    ticker_yfinance: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance chart endpoint when yfinance returns empty."""
    period1 = int(pd.Timestamp(start_date, tz="UTC").timestamp())
    period2 = int(pd.Timestamp(end_date, tz="UTC").timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_yfinance}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        )
    }
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "history",
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return pd.DataFrame()

    result = payload.get("chart", {}).get("result")
    if not result:
        return pd.DataFrame()

    timestamps = result[0].get("timestamp") or []
    quote = (result[0].get("indicators", {}).get("quote") or [{}])[0]
    if not timestamps or not quote:
        return pd.DataFrame()

    return pd.DataFrame(
        {
            "Date": pd.to_datetime(timestamps, unit="s").date,
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume"),
        }
    )

