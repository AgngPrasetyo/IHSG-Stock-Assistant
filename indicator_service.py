"""Technical indicator calculations for the final OHLCV analysis methods."""

from __future__ import annotations

import pandas as pd


def calculate_sma(df: pd.DataFrame, window: int, price_column: str = "Close") -> pd.Series:
    """Calculate a Simple Moving Average."""
    if window <= 0:
        raise ValueError("window harus lebih besar dari 0.")
    price_df = _prepare_price_dataframe(df)
    _validate_price_column(price_df, price_column)
    return price_df[price_column].rolling(window=window).mean()


def calculate_ema(df: pd.DataFrame, span: int, price_column: str = "Close") -> pd.Series:
    """Calculate an EMA; MACD uses EMA12, EMA26, and an EMA9 signal line."""
    if span <= 0:
        raise ValueError("span harus lebih besar dari 0.")
    price_df = _prepare_price_dataframe(df)
    _validate_price_column(price_df, price_column)
    return price_df[price_column].ewm(span=span, adjust=False).mean()


def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Add MACD 12/26/9 columns."""
    indicator_df = _prepare_price_dataframe(df)
    _validate_price_column(indicator_df, "Close")
    indicator_df["EMA12"] = calculate_ema(indicator_df, span=12)
    indicator_df["EMA26"] = calculate_ema(indicator_df, span=26)
    indicator_df["MACD"] = indicator_df["EMA12"] - indicator_df["EMA26"]
    indicator_df["MACD_Signal"] = indicator_df["MACD"].ewm(span=9, adjust=False).mean()
    indicator_df["MACD_Histogram"] = indicator_df["MACD"] - indicator_df["MACD_Signal"]
    return indicator_df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add an RSI column using average gain and average loss."""
    if period <= 0:
        raise ValueError("period harus lebih besar dari 0.")
    indicator_df = _prepare_price_dataframe(df)
    _validate_price_column(indicator_df, "Close")
    delta = indicator_df["Close"].diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    average_gain = gain.rolling(window=period, min_periods=period).mean()
    average_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = average_gain / average_loss
    indicator_df["RSI"] = 100 - (100 / (1 + rs))
    indicator_df.loc[(average_loss == 0) & (average_gain > 0), "RSI"] = 100
    indicator_df.loc[(average_loss == 0) & (average_gain == 0), "RSI"] = 50
    return indicator_df


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA20/SMA50, MACD 12/26/9, and RSI14 for the final methods."""
    indicator_df = _prepare_price_dataframe(df)
    indicator_df["SMA20"] = calculate_sma(indicator_df, 20)
    indicator_df["SMA50"] = calculate_sma(indicator_df, 50)
    indicator_df = calculate_macd(indicator_df)
    return calculate_rsi(indicator_df, 14)


def _prepare_price_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copied DataFrame sorted by date."""
    if df is None or df.empty:
        raise ValueError("Data harga kosong.")
    price_df = df.copy()
    if "Date" in price_df.columns:
        price_df["Date"] = pd.to_datetime(price_df["Date"])
        price_df = price_df.set_index("Date")
    if not isinstance(price_df.index, pd.DatetimeIndex):
        price_df.index = pd.to_datetime(price_df.index)
    price_df.index.name = "Date"
    return price_df.sort_index()


def _validate_price_column(df: pd.DataFrame, price_column: str) -> None:
    if price_column not in df.columns:
        raise ValueError(f"Kolom harga tidak ditemukan: {price_column}")
