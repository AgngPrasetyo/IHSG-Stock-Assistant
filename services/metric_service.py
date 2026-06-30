"""Signal evaluation metrics for deterministic technical analysis."""

from __future__ import annotations

import pandas as pd

from services.signal_service import (
    MA_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)


FORWARD_RETURN_COLUMN = "Forward_Return"
ACTUAL_DIRECTION_COLUMN = "Actual_Direction"
ACTIVE_SIGNALS = {"BUY", "SELL"}
SIGNAL_COLUMNS = [
    MA_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
]


def calculate_forward_return(
    df: pd.DataFrame,
    close_column: str = "Close",
    forward_periods: int = 1,
) -> pd.DataFrame:
    """Add forward return based on a future closing price horizon."""
    _validate_forward_periods(forward_periods)
    metric_df = _prepare_metric_dataframe(df)
    _validate_column(metric_df, close_column)

    metric_df[FORWARD_RETURN_COLUMN] = (
        metric_df[close_column].shift(-forward_periods) - metric_df[close_column]
    ) / metric_df[close_column]
    return metric_df


def calculate_actual_direction(
    df: pd.DataFrame,
    close_column: str = "Close",
    forward_periods: int = 1,
) -> pd.DataFrame:
    """Add actual future price direction from forward return."""
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


def evaluate_signal_performance(
    df: pd.DataFrame,
    signal_column: str,
    forward_periods: int = 1,
) -> dict[str, float | int | str]:
    """Evaluate BUY and SELL signal accuracy against future price direction."""
    metric_df = calculate_actual_direction(df, forward_periods=forward_periods)
    _validate_column(metric_df, signal_column)

    evaluable_rows = metric_df[metric_df[FORWARD_RETURN_COLUMN].notna()]
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


def _validate_column(df: pd.DataFrame, column: str) -> None:
    """Ensure a required column is available."""
    if column not in df.columns:
        raise ValueError(f"Kolom tidak ditemukan: {column}")


def _validate_forward_periods(forward_periods: int) -> None:
    """Ensure the evaluation horizon is a positive row count."""
    if int(forward_periods) < 1:
        raise ValueError("forward_periods harus lebih besar atau sama dengan 1.")


