"""Technical-analysis signals for final SMA10/SMA50, MACD, and RSI methods."""

from __future__ import annotations

import pandas as pd

from services.indicator_service import calculate_macd, calculate_rsi, calculate_sma

BUY, SELL, HOLD = "BUY", "SELL", "HOLD"
MA_CROSSOVER_SIGNAL_COLUMN = "MA_Crossover_Signal"
MA_SIGNAL_COLUMN = MA_CROSSOVER_SIGNAL_COLUMN  # Compatibility alias for old imports.
MACD_TRADE_SIGNAL_COLUMN = "MACD_Trade_Signal"
RSI_SIGNAL_COLUMN = "RSI_Signal"


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


def get_latest_signal(df: pd.DataFrame, indicator_name: str) -> dict[str, str]:
    """Return the latest final-method signal and deterministic reason."""
    signal_df = _ensure_indicator_signal(df, indicator_name)
    column = _get_signal_column(indicator_name)
    row = signal_df.iloc[-1]
    return {"indicator": _normalize_indicator_name(indicator_name), "signal": row[column], "date": signal_df.index[-1].strftime("%Y-%m-%d"), "reason": _build_reason(row, indicator_name)}


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


def _ensure_sma_columns(df: pd.DataFrame, *windows: int) -> pd.DataFrame:
    signal_df = df.copy()
    for window in windows:
        column = f"SMA{window}"
        if column not in signal_df.columns:
            signal_df[column] = calculate_sma(signal_df, window)
    return signal_df



def _has_current_and_previous_values(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    return df[columns].notna().all(axis=1) & df[columns].shift(1).notna().all(axis=1)


def _ensure_indicator_signal(df: pd.DataFrame, indicator_name: str) -> pd.DataFrame:
    name = _normalize_indicator_name(indicator_name)
    if name == "MA Crossover": 
        return generate_ma_signal(df)
    if name == "MACD": 
        return generate_macd_signal(df)
    return generate_rsi_signal(df)


def _get_signal_column(indicator_name: str) -> str:
    return {"MA Crossover": MA_CROSSOVER_SIGNAL_COLUMN, "MACD": MACD_TRADE_SIGNAL_COLUMN, "RSI": RSI_SIGNAL_COLUMN}[_normalize_indicator_name(indicator_name)]


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