"""Fixed-length rolling Walk-Forward Analysis service."""

from __future__ import annotations

import pandas as pd

from services.indicator_service import calculate_all_indicators
from services.metric_service import (
    DEFAULT_FORWARD_HORIZONS,
    evaluate_signal_performance_average_forward,
)
from services.signal_service import generate_all_signals

DEFAULT_IN_SAMPLE_MONTHS = 6
DEFAULT_OUT_SAMPLE_MONTHS = 3
DEFAULT_SHIFT_MONTHS = 3
DEFAULT_EVALUATION_HORIZONS = DEFAULT_FORWARD_HORIZONS
DEFAULT_WARMUP_PERIODS = 50

INDICATOR_SIGNAL_MAP = {
    "MA Crossover": "MA_Crossover_Signal",
    "MACD": "MACD_Trade_Signal",
    "RSI": "RSI_Signal",
}
WFA_RESULT_COLUMNS = [
    "window_id",
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
WFA_AGGREGATE_COLUMNS = [
    "indicator",
    "signal_column",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
]

WFA_SELECTION_COLUMNS = [
    "window_id",
    "selected_indicator",
    "selected_signal_column",
    "in_sample_start",
    "in_sample_end",
    "out_sample_start",
    "out_sample_end",
    "in_sample_total_active_signals",
    "in_sample_correct_signals",
    "in_sample_directional_accuracy",
    "in_sample_hit_rate",
    "out_sample_total_active_signals",
    "out_sample_correct_signals",
    "out_sample_directional_accuracy",
    "out_sample_hit_rate",
]


def prepare_wfa_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV input into a Date-indexed frame for fixed-length rolling WFA."""
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()
    if "Date" in result.columns:
        result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
        result = result.set_index("Date")

    if not isinstance(result.index, pd.DatetimeIndex):
        result.index = pd.to_datetime(result.index, errors="coerce")

    result = result[result.index.notna()]
    result.index.name = "Date"
    if "Close" not in result.columns:
        return pd.DataFrame()
    return result.dropna(subset=["Close"]).sort_index()


def generate_wfa_windows(
    df: pd.DataFrame,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
    evaluation_start_date: str | pd.Timestamp | None = None,
    warmup_periods: int = 0,
) -> list[dict[str, object]]:
    """
    Generate fixed-length rolling in-sample/out-sample WFA windows.

    Evaluation windows start from ``evaluation_start_date`` when provided. Rows
    before that date may be used as warm-up data for indicator calculation, but
    they are not included in in-sample or out-of-sample evaluation.
    """
    wfa_df = prepare_wfa_dataframe(df)
    if wfa_df.empty:
        return []

    windows = []
    window_id = 1

    if evaluation_start_date is None:
        start = wfa_df.index.min()
    else:
        start = pd.Timestamp(evaluation_start_date)

    data_end = wfa_df.index.max()

    while True:
        out_start = start + pd.DateOffset(months=in_sample_months)
        out_end = out_start + pd.DateOffset(months=out_sample_months)

        if data_end < out_end - pd.DateOffset(days=1):
            break

        in_df = wfa_df[(wfa_df.index >= start) & (wfa_df.index < out_start)].copy()
        out_df = wfa_df[(wfa_df.index >= out_start) & (wfa_df.index < out_end)].copy()

        if not in_df.empty and not out_df.empty:
            warmup_df = _get_warmup_dataframe(wfa_df, start, warmup_periods)
            frames = [frame for frame in (warmup_df, in_df, out_df) if not frame.empty]
            combined_df = pd.concat(frames).sort_index()
            combined_df = combined_df[~combined_df.index.duplicated(keep="last")]
            combined_df.index.name = "Date"

            windows.append(
                {
                    "window_id": window_id,
                    "warmup_start": None if warmup_df.empty else warmup_df.index.min(),
                    "warmup_end": None if warmup_df.empty else warmup_df.index.max(),
                    "in_sample_start": start,
                    "in_sample_end": out_start - pd.DateOffset(days=1),
                    "out_sample_start": out_start,
                    "out_sample_end": out_end,
                    "warmup_df": warmup_df,
                    "in_sample_df": in_df,
                    "out_sample_df": out_df,
                    "combined_df": combined_df,
                }
            )
            window_id += 1

        start = start + pd.DateOffset(months=shift_months)

    return windows

def _get_warmup_dataframe(
    df: pd.DataFrame,
    evaluation_start: pd.Timestamp,
    warmup_periods: int,
) -> pd.DataFrame:
    """Return the latest warm-up rows before the evaluation period starts."""
    periods = max(0, int(warmup_periods))
    if periods == 0:
        return pd.DataFrame(columns=df.columns)

    warmup_df = df[df.index < evaluation_start].tail(periods).copy()
    return warmup_df

def run_wfa_for_window(
    window: dict[str, object],
    evaluation_horizons: list[int] | tuple[int, ...] | None = None,
) -> list[dict[str, object]]:
    """Evaluate every final indicator inside one fixed-length WFA window."""
    combined = window.get("combined_df")
    out_df = window.get("out_sample_df")
    if (
        not isinstance(combined, pd.DataFrame)
        or combined.empty
        or not isinstance(out_df, pd.DataFrame)
        or out_df.empty
    ):
        return []

    signal_df = generate_all_signals(calculate_all_indicators(combined))
    evaluation = signal_df.loc[signal_df.index.isin(out_df.index)].copy()
    results = []

    for indicator, column in INDICATOR_SIGNAL_MAP.items():
        metric = evaluate_signal_performance_average_forward(
            evaluation,
            column,
            forward_horizons=evaluation_horizons,
        )
        results.append(
            {
                "window_id": int(window["window_id"]),
                "indicator": indicator,
                "signal_column": column,
                "in_sample_start": _format_date(window["in_sample_start"]),
                "in_sample_end": _format_date(window["in_sample_end"]),
                "out_sample_start": _format_date(window["out_sample_start"]),
                "out_sample_end": _format_date(window["out_sample_end"]),
                "total_active_signals": int(metric["total_active_signals"]),
                "correct_signals": int(metric["correct_signals"]),
                "directional_accuracy": float(metric["directional_accuracy"]),
                "hit_rate": float(metric["hit_rate"]),
            }
        )

    return results

def evaluate_indicators_on_period(
    signal_df: pd.DataFrame,
    period_df: pd.DataFrame,
    evaluation_horizons: list[int] | tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """
    Evaluate all final indicators on a selected period.

    The signal columns are calculated on the full window data, but the metric is
    measured only on the rows that belong to the requested period. This allows
    the same prepared indicator data to be evaluated separately on in-sample and
    out-of-sample periods.
    """
    if (
        not isinstance(signal_df, pd.DataFrame)
        or signal_df.empty
        or not isinstance(period_df, pd.DataFrame)
        or period_df.empty
    ):
        return pd.DataFrame(columns=WFA_AGGREGATE_COLUMNS)

    evaluation = signal_df.loc[signal_df.index.isin(period_df.index)].copy()
    if evaluation.empty:
        return pd.DataFrame(columns=WFA_AGGREGATE_COLUMNS)

    results = []
    for indicator, column in INDICATOR_SIGNAL_MAP.items():
        metric = evaluate_signal_performance_average_forward(
            evaluation,
            column,
            forward_horizons=evaluation_horizons,
        )
        results.append(
            {
                "indicator": indicator,
                "signal_column": column,
                "total_active_signals": int(metric["total_active_signals"]),
                "correct_signals": int(metric["correct_signals"]),
                "directional_accuracy": float(metric["directional_accuracy"]),
                "hit_rate": float(metric["hit_rate"]),
            }
        )

    return pd.DataFrame(results, columns=WFA_AGGREGATE_COLUMNS)


def run_wfa_selection_for_window(
    window: dict[str, object],
    evaluation_horizons: list[int] | tuple[int, ...] | None = None,
) -> dict[str, object] | None:
    """
    Select the best indicator on in-sample data and validate it on out-sample data.

    This is the stricter WFA workflow:
    1. All candidate indicators are evaluated on the in-sample period.
    2. The best in-sample indicator is selected using Directional Accuracy,
       Hit Rate, and Total Active Signals as tie-breakers.
    3. Only the selected indicator is evaluated on the out-of-sample period.
    """
    combined = window.get("combined_df")
    in_df = window.get("in_sample_df")
    out_df = window.get("out_sample_df")

    if (
        not isinstance(combined, pd.DataFrame)
        or combined.empty
        or not isinstance(in_df, pd.DataFrame)
        or in_df.empty
        or not isinstance(out_df, pd.DataFrame)
        or out_df.empty
    ):
        return None

    signal_df = generate_all_signals(calculate_all_indicators(combined))

    in_sample_results = evaluate_indicators_on_period(
        signal_df,
        in_df,
        evaluation_horizons=evaluation_horizons,
    )
    if in_sample_results.empty:
        return None

    selected = select_best_indicator(in_sample_results)
    if not selected:
        return None

    out_sample_results = evaluate_indicators_on_period(
        signal_df,
        out_df,
        evaluation_horizons=evaluation_horizons,
    )
    if out_sample_results.empty:
        return None

    selected_out = out_sample_results[
        out_sample_results["indicator"] == selected["indicator"]
    ]
    if selected_out.empty:
        return None

    out_row = selected_out.iloc[0]

    return {
        "window_id": int(window["window_id"]),
        "selected_indicator": selected["indicator"],
        "selected_signal_column": selected["signal_column"],
        "in_sample_start": _format_date(window["in_sample_start"]),
        "in_sample_end": _format_date(window["in_sample_end"]),
        "out_sample_start": _format_date(window["out_sample_start"]),
        "out_sample_end": _format_date(window["out_sample_end"]),
        "in_sample_total_active_signals": int(selected["total_active_signals"]),
        "in_sample_correct_signals": int(selected["correct_signals"]),
        "in_sample_directional_accuracy": float(selected["directional_accuracy"]),
        "in_sample_hit_rate": float(selected["hit_rate"]),
        "out_sample_total_active_signals": int(out_row["total_active_signals"]),
        "out_sample_correct_signals": int(out_row["correct_signals"]),
        "out_sample_directional_accuracy": float(out_row["directional_accuracy"]),
        "out_sample_hit_rate": float(out_row["hit_rate"]),
    }

def run_wfa_selection_pipeline(
    df: pd.DataFrame,
    evaluation_horizons: list[int] | tuple[int, ...] | None = None,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
    evaluation_start_date: str | pd.Timestamp | None = None,
    warmup_periods: int = 0,
) -> dict[str, object]:
    """
    Run WFA with in-sample indicator selection and out-of-sample validation.

    This pipeline keeps the stricter workflow:
    1. Generate fixed-length WFA windows.
    2. Select the best indicator from each in-sample window.
    3. Validate only the selected indicator on the out-sample window.
    """
    windows = generate_wfa_windows(
        df,
        in_sample_months,
        out_sample_months,
        shift_months,
        evaluation_start_date=evaluation_start_date,
        warmup_periods=warmup_periods,
    )

    results = []
    for window in windows:
        result = run_wfa_selection_for_window(
            window,
            evaluation_horizons=evaluation_horizons,
        )
        if result is not None:
            results.append(result)

    selection_results = pd.DataFrame(results, columns=WFA_SELECTION_COLUMNS)

    return {
        "windows_count": len(windows),
        "selection_results": selection_results,
    }


def run_wfa_all_indicators(
    df: pd.DataFrame,
    evaluation_horizons: list[int] | tuple[int, ...] | None = None,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> pd.DataFrame:
    """Run all final indicators across all fixed-length rolling WFA windows."""
    windows = generate_wfa_windows(df, in_sample_months, out_sample_months, shift_months)
    results = []
    for window in windows:
        results.extend(run_wfa_for_window(window, evaluation_horizons))

    if not results:
        return pd.DataFrame(columns=WFA_RESULT_COLUMNS)
    return pd.DataFrame(results, columns=WFA_RESULT_COLUMNS)


def aggregate_wfa_results(wfa_results_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate window-level WFA counts into indicator-level metrics."""
    if wfa_results_df is None or wfa_results_df.empty:
        return pd.DataFrame(columns=WFA_AGGREGATE_COLUMNS)

    group_keys = ["indicator", "signal_column"]
    result = (
        wfa_results_df.groupby(group_keys, as_index=False)[
            ["total_active_signals", "correct_signals"]
        ]
        .sum()
        .sort_values("indicator")
        .reset_index(drop=True)
    )
    result["directional_accuracy"] = result.apply(_calculate_count_based_score, axis=1)
    result = result.merge(
        _average_active_hit_rate(wfa_results_df, group_keys),
        on=group_keys,
        how="left",
    )
    result["hit_rate"] = result["hit_rate"].fillna(0.0)
    return result[WFA_AGGREGATE_COLUMNS]


def select_best_indicator(aggregate_df: pd.DataFrame) -> dict[str, object] | None:
    """Select the best indicator using the locked metric tie-break order."""
    if aggregate_df is None or aggregate_df.empty:
        return None

    row = aggregate_df.sort_values(
        ["directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False],
    ).iloc[0]
    return {
        "indicator": row["indicator"],
        "signal_column": row["signal_column"],
        "directional_accuracy": float(row["directional_accuracy"]),
        "hit_rate": float(row["hit_rate"]),
        "total_active_signals": int(row["total_active_signals"]),
        "correct_signals": int(row["correct_signals"]),
    }


def run_wfa_pipeline(
    df: pd.DataFrame,
    evaluation_horizons: list[int] | tuple[int, ...] | None = None,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> dict[str, object]:
    """Run the complete fixed-length rolling WFA workflow for one stock."""
    windows = generate_wfa_windows(df, in_sample_months, out_sample_months, shift_months)
    results = run_wfa_all_indicators(
        df,
        evaluation_horizons,
        in_sample_months,
        out_sample_months,
        shift_months,
    )
    aggregate = aggregate_wfa_results(results)
    return {
        "windows_count": len(windows),
        "wfa_results": results,
        "aggregate_results": aggregate,
        "best_indicator": select_best_indicator(aggregate),
    }


def _calculate_count_based_score(row: pd.Series) -> float:
    """Return count-based percentage accuracy from active/correct signal counts."""
    total_active = int(row["total_active_signals"])
    if total_active == 0:
        return 0.0
    return int(row["correct_signals"]) / total_active * 100


def _average_active_hit_rate(df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    """Return Average Window Hit Rate for rows with active BUY/SELL signals."""
    active = df[df["total_active_signals"] > 0]
    if active.empty:
        return pd.DataFrame(columns=[*group_keys, "hit_rate"])
    return active.groupby(group_keys, as_index=False)["hit_rate"].mean().reset_index(drop=True)


def _format_date(value: object) -> str:
    """Format WFA boundary timestamps for JSON/CSV-ready outputs."""
    return pd.Timestamp(value).strftime("%Y-%m-%d")
