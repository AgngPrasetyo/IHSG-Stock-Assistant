"""Fixed-length rolling Walk-Forward Analysis service."""

from __future__ import annotations

import pandas as pd

from services.indicator_service import calculate_all_indicators
from services.metric_service import evaluate_signal_performance
from services.signal_service import generate_all_signals

DEFAULT_IN_SAMPLE_MONTHS = 6
DEFAULT_OUT_SAMPLE_MONTHS = 3
DEFAULT_SHIFT_MONTHS = 3

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
) -> list[dict[str, object]]:
    """Generate fixed-length rolling in-sample/out-sample WFA windows.

    The window moves forward by ``shift_months`` each iteration while preserving
    the locked in-sample and out-sample month lengths. Date boundaries are kept
    identical to the original implementation: in-sample is left-closed/right-open,
    out-sample is left-closed/right-open, and the reported in-sample end is one
    calendar day before out-sample start.
    """
    wfa_df = prepare_wfa_dataframe(df)
    if wfa_df.empty:
        return []

    windows = []
    window_id = 1
    start = wfa_df.index.min()
    data_end = wfa_df.index.max()

    while True:
        out_start = start + pd.DateOffset(months=in_sample_months)
        out_end = out_start + pd.DateOffset(months=out_sample_months)
        if data_end < out_end - pd.DateOffset(days=1):
            break

        in_df = wfa_df[(wfa_df.index >= start) & (wfa_df.index < out_start)].copy()
        out_df = wfa_df[(wfa_df.index >= out_start) & (wfa_df.index < out_end)].copy()
        if not in_df.empty and not out_df.empty:
            windows.append(
                {
                    "window_id": window_id,
                    "in_sample_start": start,
                    "in_sample_end": out_start - pd.DateOffset(days=1),
                    "out_sample_start": out_start,
                    "out_sample_end": out_end,
                    "in_sample_df": in_df,
                    "out_sample_df": out_df,
                    "combined_df": pd.concat([in_df, out_df]).sort_index(),
                }
            )
            window_id += 1

        start = start + pd.DateOffset(months=shift_months)

    return windows


def run_wfa_for_window(
    window: dict[str, object],
    evaluation_horizon_periods: int = 3,
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
        metric = evaluate_signal_performance(
            evaluation,
            column,
            forward_periods=evaluation_horizon_periods,
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


def run_wfa_all_indicators(
    df: pd.DataFrame,
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> pd.DataFrame:
    """Run all final indicators across all fixed-length rolling WFA windows."""
    windows = generate_wfa_windows(df, in_sample_months, out_sample_months, shift_months)
    results = []
    for window in windows:
        results.extend(run_wfa_for_window(window, evaluation_horizon_periods))

    if not results:
        return pd.DataFrame(columns=WFA_RESULT_COLUMNS)
    return pd.DataFrame(results, columns=WFA_RESULT_COLUMNS)


def aggregate_wfa_results(wfa_results_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate window-level WFA counts into indicator-level metrics."""
    if wfa_results_df is None or wfa_results_df.empty:
        return pd.DataFrame(columns=WFA_AGGREGATE_COLUMNS)

    result = (
        wfa_results_df.groupby(["indicator", "signal_column"], as_index=False)[
            ["total_active_signals", "correct_signals"]
        ]
        .sum()
        .sort_values("indicator")
        .reset_index(drop=True)
    )
    result["directional_accuracy"] = result.apply(_calculate_count_based_score, axis=1)
    result["hit_rate"] = result["directional_accuracy"]
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
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> dict[str, object]:
    """Run the complete fixed-length rolling WFA workflow for one stock.

    The pipeline only composes existing steps: generate rolling windows, evaluate
    all indicators per window, aggregate count-based metrics, and select the best
    indicator with the existing tie-break order.
    """
    windows = generate_wfa_windows(df, in_sample_months, out_sample_months, shift_months)
    results = run_wfa_all_indicators(
        df,
        evaluation_horizon_periods,
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


def _format_date(value: object) -> str:
    """Format WFA boundary timestamps for JSON/CSV-ready outputs."""
    return pd.Timestamp(value).strftime("%Y-%m-%d")
