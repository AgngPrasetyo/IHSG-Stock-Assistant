"""Sector-level aggregation service for final 6,3,3 Walk-Forward Analysis."""

from __future__ import annotations

import pandas as pd

from services.data_service import load_or_fetch_price_data
from services.mapping_service import load_mapping
from services.wfa_service import (
    DEFAULT_IN_SAMPLE_MONTHS,
    DEFAULT_OUT_SAMPLE_MONTHS,
    DEFAULT_SHIFT_MONTHS,
    run_wfa_pipeline,
)

SECTOR_RESULT_COLUMNS = [
    "sektor",
    "ticker",
    "ticker_yfinance",
    "indicator",
    "signal_column",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
    "windows_count",
]
SECTOR_WINDOW_RESULT_COLUMNS = [
    "sektor",
    "ticker",
    "ticker_yfinance",
    "indicator",
    "signal_column",
    "window_id",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
]
SECTOR_AGGREGATE_COLUMNS = [
    "sektor",
    "indicator",
    "signal_column",
    "total_stocks",
    "total_windows",
    "total_active_signals",
    "correct_signals",
    "directional_accuracy",
    "hit_rate",
]
_REQUIRED_STOCK_COLUMNS = ["ticker", "ticker_yfinance", "sektor"]


def get_available_sectors(mapping_df: pd.DataFrame | None = None) -> list[str]:
    """Return sorted sectors that have complete sample stocks in the mapping."""
    sample = _get_complete_sample_mapping(mapping_df)
    if sample.empty:
        return []

    sectors = sample["sektor"].dropna().astype(str).str.strip().unique()
    return sorted(sector for sector in sectors if sector)


def get_sector_stocks(sector: str, mapping_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return complete sample stocks for one sector using the public mapping columns."""
    sample = _get_complete_sample_mapping(mapping_df)
    if sample.empty or not sector:
        return pd.DataFrame(columns=_REQUIRED_STOCK_COLUMNS)

    normalized_sector = str(sector).strip().lower()
    result = sample[
        sample["sektor"].astype(str).str.strip().str.lower() == normalized_sector
    ].copy()

    if result.empty:
        return pd.DataFrame(columns=_REQUIRED_STOCK_COLUMNS)
    return result[_REQUIRED_STOCK_COLUMNS].reset_index(drop=True)


def run_wfa_for_stock_row(
    stock_row: pd.Series | dict[str, object],
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> pd.DataFrame:
    """Run WFA for one mapped stock row and attach ticker/sector metadata."""
    try:
        row = pd.Series(stock_row)
        price_df = load_or_fetch_price_data(str(row["ticker_yfinance"]).strip())
        wfa = run_wfa_pipeline(
            price_df,
            evaluation_horizon_periods,
            in_sample_months,
            out_sample_months,
            shift_months,
        )
        aggregate = wfa.get("aggregate_results")
        if not isinstance(aggregate, pd.DataFrame) or aggregate.empty:
            return pd.DataFrame(columns=SECTOR_RESULT_COLUMNS)

        result = aggregate.copy()
        result["ticker"] = str(row["ticker"]).strip()
        result["ticker_yfinance"] = str(row["ticker_yfinance"]).strip()
        result["sektor"] = str(row["sektor"]).strip()
        result["windows_count"] = int(wfa.get("windows_count", 0))
        return result[SECTOR_RESULT_COLUMNS]
    except Exception:
        return pd.DataFrame(columns=SECTOR_RESULT_COLUMNS)


def run_wfa_windows_for_stock_row(
    stock_row: pd.Series | dict[str, object],
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> pd.DataFrame:
    """Run WFA for one mapped stock row and return raw window-level metrics."""
    try:
        row = pd.Series(stock_row)
        price_df = load_or_fetch_price_data(str(row["ticker_yfinance"]).strip())
        wfa = run_wfa_pipeline(
            price_df,
            evaluation_horizon_periods,
            in_sample_months,
            out_sample_months,
            shift_months,
        )
        window_results = wfa.get("wfa_results")
        if not isinstance(window_results, pd.DataFrame) or window_results.empty:
            return pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS)

        result = window_results.copy()
        result["ticker"] = str(row["ticker"]).strip()
        result["ticker_yfinance"] = str(row["ticker_yfinance"]).strip()
        result["sektor"] = str(row["sektor"]).strip()
        return result[SECTOR_WINDOW_RESULT_COLUMNS]
    except Exception:
        return pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS)


def run_wfa_outputs_for_stock_row(
    stock_row: pd.Series | dict[str, object],
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run WFA once and return stock-level plus window-level rows."""
    try:
        row = pd.Series(stock_row)
        price_df = load_or_fetch_price_data(str(row["ticker_yfinance"]).strip())
        wfa = run_wfa_pipeline(
            price_df,
            evaluation_horizon_periods,
            in_sample_months,
            out_sample_months,
            shift_months,
        )

        aggregate = wfa.get("aggregate_results")
        window_results = wfa.get("wfa_results")
        if not isinstance(aggregate, pd.DataFrame) or aggregate.empty:
            return (
                pd.DataFrame(columns=SECTOR_RESULT_COLUMNS),
                pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS),
            )

        stock_result = aggregate.copy()
        stock_result["ticker"] = str(row["ticker"]).strip()
        stock_result["ticker_yfinance"] = str(row["ticker_yfinance"]).strip()
        stock_result["sektor"] = str(row["sektor"]).strip()
        stock_result["windows_count"] = int(wfa.get("windows_count", 0))

        if isinstance(window_results, pd.DataFrame) and not window_results.empty:
            window_result = window_results.copy()
            window_result["ticker"] = str(row["ticker"]).strip()
            window_result["ticker_yfinance"] = str(row["ticker_yfinance"]).strip()
            window_result["sektor"] = str(row["sektor"]).strip()
            window_result = window_result[SECTOR_WINDOW_RESULT_COLUMNS]
        else:
            window_result = pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS)

        return stock_result[SECTOR_RESULT_COLUMNS], window_result
    except Exception:
        return (
            pd.DataFrame(columns=SECTOR_RESULT_COLUMNS),
            pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS),
        )


def run_sector_wfa(
    sector: str,
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> pd.DataFrame:
    """Run per-stock WFA for every complete sample stock in a sector."""
    stocks = get_sector_stocks(sector)
    frames = [
        run_wfa_for_stock_row(
            row,
            evaluation_horizon_periods,
            in_sample_months,
            out_sample_months,
            shift_months,
        )
        for _, row in stocks.iterrows()
    ]
    frames = [frame for frame in frames if not frame.empty]

    if not frames:
        return pd.DataFrame(columns=SECTOR_RESULT_COLUMNS)
    return pd.concat(frames, ignore_index=True)[SECTOR_RESULT_COLUMNS]


def run_sector_wfa_windows(
    sector: str,
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> pd.DataFrame:
    """Run per-stock WFA and return all raw window-level rows for a sector."""
    stocks = get_sector_stocks(sector)
    frames = [
        run_wfa_windows_for_stock_row(
            row,
            evaluation_horizon_periods,
            in_sample_months,
            out_sample_months,
            shift_months,
        )
        for _, row in stocks.iterrows()
    ]
    frames = [frame for frame in frames if not frame.empty]

    if not frames:
        return pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS)
    return pd.concat(frames, ignore_index=True)[SECTOR_WINDOW_RESULT_COLUMNS]


def run_sector_wfa_outputs(
    sector: str,
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run per-stock WFA once and return stock-level plus window-level sector rows."""
    stocks = get_sector_stocks(sector)
    stock_frames = []
    window_frames = []
    for _, row in stocks.iterrows():
        stock_result, window_result = run_wfa_outputs_for_stock_row(
            row,
            evaluation_horizon_periods,
            in_sample_months,
            out_sample_months,
            shift_months,
        )
        if not stock_result.empty:
            stock_frames.append(stock_result)
        if not window_result.empty:
            window_frames.append(window_result)

    stock_results = (
        pd.concat(stock_frames, ignore_index=True)[SECTOR_RESULT_COLUMNS]
        if stock_frames
        else pd.DataFrame(columns=SECTOR_RESULT_COLUMNS)
    )
    window_results = (
        pd.concat(window_frames, ignore_index=True)[SECTOR_WINDOW_RESULT_COLUMNS]
        if window_frames
        else pd.DataFrame(columns=SECTOR_WINDOW_RESULT_COLUMNS)
    )
    return stock_results, window_results


def aggregate_sector_results(sector_results_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate WFA rows into sector-level indicator metrics."""
    if sector_results_df is None or sector_results_df.empty:
        return pd.DataFrame(columns=SECTOR_AGGREGATE_COLUMNS)

    group_keys = ["sektor", "indicator", "signal_column"]
    is_window_level = "window_id" in sector_results_df.columns
    window_source = "window_id" if is_window_level else "windows_count"
    window_agg = "count" if is_window_level else "sum"
    result = (
        sector_results_df.groupby(group_keys, as_index=False)
        .agg(
            total_stocks=("ticker", "nunique"),
            total_windows=(window_source, window_agg),
            total_active_signals=("total_active_signals", "sum"),
            correct_signals=("correct_signals", "sum"),
        )
        .sort_values(["sektor", "indicator"])
        .reset_index(drop=True)
    )
    result["directional_accuracy"] = result.apply(_calculate_count_based_score, axis=1)
    result = result.merge(
        _average_active_hit_rate(sector_results_df, group_keys),
        on=group_keys,
        how="left",
    )
    result["hit_rate"] = pd.to_numeric(result["hit_rate"], errors="coerce").fillna(0.0)
    return result[SECTOR_AGGREGATE_COLUMNS]


def select_best_sector_indicator(sector_aggregate_df: pd.DataFrame) -> dict[str, object] | None:
    """Select the best sector indicator using the existing metric tie-break order."""
    if sector_aggregate_df is None or sector_aggregate_df.empty:
        return None

    row = sector_aggregate_df.sort_values(
        ["directional_accuracy", "hit_rate", "total_active_signals"],
        ascending=[False, False, False],
    ).iloc[0]
    return {
        "sektor": row["sektor"],
        "indicator": row["indicator"],
        "signal_column": row["signal_column"],
        "total_stocks": int(row["total_stocks"]),
        "total_windows": int(row["total_windows"]),
        "total_active_signals": int(row["total_active_signals"]),
        "correct_signals": int(row["correct_signals"]),
        "directional_accuracy": float(row["directional_accuracy"]),
        "hit_rate": float(row["hit_rate"]),
    }


def run_sector_pipeline(
    sector: str,
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> dict[str, object]:
    """Run the sector workflow: stocks, WFA rows, aggregate rows, best indicator."""
    stocks = get_sector_stocks(sector)
    results, window_results = run_sector_wfa_outputs(
        sector,
        evaluation_horizon_periods,
        in_sample_months,
        out_sample_months,
        shift_months,
    )
    aggregate_source = window_results if not window_results.empty else results
    aggregate = aggregate_sector_results(aggregate_source)
    return {
        "sector": sector,
        "stocks_count": int(len(stocks)),
        "sector_results": results,
        "sector_window_results": window_results,
        "sector_aggregate": aggregate,
        "best_indicator": select_best_sector_indicator(aggregate),
    }


def run_all_sectors_pipeline(
    evaluation_horizon_periods: int = 3,
    in_sample_months: int = DEFAULT_IN_SAMPLE_MONTHS,
    out_sample_months: int = DEFAULT_OUT_SAMPLE_MONTHS,
    shift_months: int = DEFAULT_SHIFT_MONTHS,
) -> dict[str, object]:
    """Run the sector pipeline for every available complete sample sector."""
    sectors = get_available_sectors()
    return {
        "sectors_count": len(sectors),
        "sectors": sectors,
        "results_by_sector": {
            sector: run_sector_pipeline(
                sector,
                evaluation_horizon_periods,
                in_sample_months,
                out_sample_months,
                shift_months,
            )
            for sector in sectors
        },
    }


def _get_complete_sample_mapping(mapping_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return only complete sample rows required by sector-level WFA."""
    mapping = load_mapping() if mapping_df is None else mapping_df.copy()
    required = {"ticker", "ticker_yfinance", "sektor", "status_data", "is_sample"}
    if mapping is None or mapping.empty or not required.issubset(mapping.columns):
        return pd.DataFrame()

    complete = mapping["status_data"].astype(str).str.strip().str.lower() == "lengkap"
    sample = mapping["is_sample"].astype(str).str.strip().str.lower() == "ya"
    return mapping[complete & sample].copy().reset_index(drop=True)


def _calculate_count_based_score(row: pd.Series) -> float:
    """Return count-based percentage accuracy from aggregated signal counts."""
    total_active = int(row["total_active_signals"])
    if total_active == 0:
        return 0.0
    return int(row["correct_signals"]) / total_active * 100


def _average_active_hit_rate(df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    """Return average stock/window hit rate for rows with active BUY/SELL signals."""
    active = df[df["total_active_signals"] > 0]
    if active.empty:
        return pd.DataFrame(columns=[*group_keys, "hit_rate"])
    return active.groupby(group_keys, as_index=False)["hit_rate"].mean().reset_index(drop=True)
