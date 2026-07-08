"""Signal evaluation metrics for deterministic technical analysis."""

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