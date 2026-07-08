"""Compose deterministic stock-analysis payloads from cached data and WFA outputs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from services.data_service import (
    END_DATE,
    REQUIRED_OHLCV_COLUMNS,
    START_DATE,
    load_or_fetch_price_data,
)
from services.indicator_service import calculate_all_indicators
from services.mapping_service import get_stock_info, normalize_ticker, resolve_ticker
from services.post_signal_validation_service import build_post_signal_validation
from services.technical_hint_service import get_indicator_hint
from services.signal_service import (
    MACD_TRADE_SIGNAL_COLUMN,
    MA_CROSSOVER_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
    generate_ma_signal,
    generate_macd_signal,
    generate_rsi_signal,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATE_RANGE_LABEL = f"{START_DATE}_{END_DATE}"

SECTOR_AGGREGATE_PATH = DATA_DIR / f"wfa_sector_aggregate_{DATE_RANGE_LABEL}.csv"
BEST_INDICATOR_PATH = DATA_DIR / f"wfa_best_indicator_by_sector_{DATE_RANGE_LABEL}.csv"
SUMMARY_PATH = DATA_DIR / f"wfa_summary_{DATE_RANGE_LABEL}.csv"

WFA_CONFIG = {
    "in_sample_months": 6,
    "out_sample_months": 3,
    "shift_months": 3,
    "evaluation_method": "Average Forward Return",
    "evaluation_horizons": [1, 3, 5, 10],
    "evaluation_horizon_label": "T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham",
    "evaluation_horizon_periods": None,
}
DATA_PERIOD = {
    "start_date": START_DATE,
    "end_date": END_DATE,
    "end_date_exclusive": True,
}
POST_SIGNAL_VALIDATION_END_DATE = "2026-07-11"
DISCLAIMER = "Hasil ini merupakan sinyal analisis teknikal, bukan rekomendasi investasi final."

INDICATOR_SIGNAL_COLUMNS = {
    "MA Crossover": MA_CROSSOVER_SIGNAL_COLUMN,
    "MACD": MACD_TRADE_SIGNAL_COLUMN,
    "RSI": RSI_SIGNAL_COLUMN,
}
INDICATOR_ORDER = ["MA Crossover", "MACD", "RSI"]
CHART_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "SMA10",
    "SMA50",
    "Volume_MA20",
    "MACD",
    "MACD_Signal",
    "MACD_Histogram",
    "RSI",
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
]


def load_wfa_outputs() -> dict[str, pd.DataFrame]:
    """Load the neutral sector-level WFA CSV outputs created by the main runner."""
    paths = {
        "sector_aggregate": SECTOR_AGGREGATE_PATH,
        "best_indicator_by_sector": BEST_INDICATOR_PATH,
        "summary": SUMMARY_PATH,
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"File output WFA belum tersedia: {', '.join(missing)}")

    try:
        return {name: pd.read_csv(path) for name, path in paths.items()}
    except (OSError, pd.errors.ParserError) as exc:
        raise ValueError("File output WFA tidak dapat dibaca.") from exc


def extract_ticker_from_text(user_input: str | None) -> str | None:
    """Resolve a supported IDX ticker from ticker text, company name, or alias."""
    resolved = resolve_ticker(user_input)
    if resolved:
        return resolved

    normalized = normalize_ticker(user_input)
    if not normalized or not re.fullmatch(r"[A-Z0-9]{2,6}", normalized):
        return None
    return normalized


def get_sector_best_indicator(sector_name: str) -> dict[str, Any] | None:
    """Return the best WFA indicator for a sector, or None when unavailable."""
    best_df = load_wfa_outputs()["best_indicator_by_sector"]
    row = _find_sector_row(best_df, sector_name)
    if row is None:
        return None
    return _record(row, [
        "sektor", "indicator", "signal_column", "directional_accuracy", "hit_rate",
        "total_active_signals", "correct_signals",
    ], sector_key="sector")


def get_sector_indicator_comparison(sector_name: str) -> list[dict[str, Any]]:
    """Return all final-indicator WFA metrics for a sector."""
    aggregate_df = load_wfa_outputs()["sector_aggregate"]
    if not sector_name or "sektor" not in aggregate_df.columns:
        return []

    rows = aggregate_df[
        aggregate_df["sektor"].astype(str).str.strip().str.casefold()
        == str(sector_name).strip().casefold()
    ].copy()
    if rows.empty:
        return []

    rows["_order"] = pd.Categorical(rows["indicator"], INDICATOR_ORDER, ordered=True)
    rows = rows.sort_values("_order")
    return [
        _record(row, [
            "indicator", "directional_accuracy", "hit_rate", "total_active_signals", "correct_signals",
        ])
        for _, row in rows.iterrows()
    ]


def prepare_latest_analysis_dataframe(ticker_yfinance: str) -> pd.DataFrame:
    """Load cached/latest OHLCV data and add final indicators and signal columns."""
    price_df = load_or_fetch_price_data(ticker_yfinance, use_cache=True)
    analysis_df = price_df.dropna(subset=REQUIRED_OHLCV_COLUMNS).copy()

    if analysis_df.empty:
        raise ValueError("Data OHLCV lengkap tidak tersedia untuk analisis.")

    analysis_df = calculate_all_indicators(analysis_df)
    analysis_df = generate_ma_signal(analysis_df)
    analysis_df = generate_macd_signal(analysis_df)
    return generate_rsi_signal(analysis_df)

def prepare_post_signal_validation_dataframe(ticker_yfinance: str) -> pd.DataFrame:
    """Load extended cached OHLCV data only for validating already-formed signals."""
    price_df = load_or_fetch_price_data(
        ticker_yfinance,
        start_date=START_DATE,
        end_date=POST_SIGNAL_VALIDATION_END_DATE,
        use_cache=True,
    )
    analysis_df = price_df.dropna(subset=REQUIRED_OHLCV_COLUMNS).copy()

    if analysis_df.empty:
        raise ValueError("Data OHLCV lengkap tidak tersedia untuk validasi lanjutan.")

    analysis_df = calculate_all_indicators(analysis_df)
    analysis_df = generate_ma_signal(analysis_df)
    analysis_df = generate_macd_signal(analysis_df)
    return generate_rsi_signal(analysis_df)

def get_last_active_signal(df: pd.DataFrame, signal_column: str) -> dict[str, Any] | None:
    """Return the latest BUY/SELL signal from the final signal column."""
    if df is None or df.empty or signal_column not in df.columns:
        return None

    active_df = df[df[signal_column].astype(str).str.upper().isin({"BUY", "SELL"})].copy()
    if active_df.empty:
        return None

    last_date = active_df.index[-1]
    last_row = active_df.iloc[-1]
    signal = str(last_row.get(signal_column, "")).upper()

    return {
        "signal": signal,
        "date": pd.Timestamp(last_date).strftime("%Y-%m-%d"),
        "close": _json_value(last_row.get("Close")),
    }


def get_latest_signal_by_indicator(df: pd.DataFrame, indicator_name: str) -> str:
    """Return the latest BUY, SELL, or HOLD value for a final indicator."""
    column = _get_signal_column(indicator_name)
    if df is None or df.empty or column not in df.columns:
        return "HOLD"
    signal = str(df.iloc[-1][column]).upper()
    return signal if signal in {"BUY", "SELL", "HOLD"} else "HOLD"


def build_latest_condition(df: pd.DataFrame, indicator_name: str) -> str:
    """Build a short deterministic description of the latest indicator state."""
    if df is None or df.empty:
        return "Data indikator terkini belum tersedia."

    row = df.iloc[-1]
    name = _normalize_indicator_name(indicator_name)
    signal = get_latest_signal_by_indicator(df, name)
    close = _format_number(row.get("Close"))
    sma50 = _format_number(row.get("SMA50"))

    if name == "MA Crossover":
        sma10 = _format_number(row.get("SMA10"))
        position = _relative_position(row.get("SMA10"), row.get("SMA50"), "SMA10", "SMA50")

        signal_note = (
            "Sinyal HOLD karena tidak ada crossover baru antara SMA10 dan SMA50 pada data terakhir."
            if signal == "HOLD"
            else f"Sinyal {signal} muncul karena terjadi crossover baru antara SMA10 dan SMA50."
        )

        return (
            f"Close {close}; SMA10 {sma10}; SMA50 {sma50}. "
            f"{position}. {signal_note}"
        )
    if name == "MACD":
        macd = _format_number(row.get("MACD"))
        macd_signal = _format_number(row.get("MACD_Signal"))
        histogram = _format_number(row.get("MACD_Histogram"))

        macd_position = _relative_position(
            row.get("MACD"),
            row.get("MACD_Signal"),
            "MACD Line",
            "Signal Line",
        )

        signal_note = (
            "Sinyal HOLD karena tidak ada crossover baru antara MACD Line dan Signal Line pada data terakhir."
            if signal == "HOLD"
            else f"Sinyal {signal} muncul karena terjadi crossover baru antara MACD Line dan Signal Line."
        )

        return (
            f"MACD Line {macd}; Signal Line {macd_signal}; Histogram {histogram}. "
            f"{macd_position}. {signal_note}"
        )

    rsi = _format_number(row.get("RSI"))
    rsi_state = _rsi_state(row.get("RSI"))
    signal_note = _rsi_signal_note(signal, rsi_state)
    return f"RSI {rsi} dengan status {rsi_state}. {signal_note}"


def build_chart_data(df: pd.DataFrame, limit: int = 120) -> list[dict[str, Any]]:
    """Return JSON-serializable OHLCV, final indicator, and signal chart points."""
    if df is None or df.empty:
        return []

    chart_df = df.tail(max(0, int(limit))).copy()
    result = []
    for date, row in chart_df.iterrows():
        point = {"date": pd.Timestamp(date).strftime("%Y-%m-%d")}
        for column in CHART_COLUMNS:
            point[_chart_key(column)] = _json_value(row.get(column))
        result.append(point)
    return result


def _build_validation_dataframe(
    ticker_yfinance: str,
    analysis_df: pd.DataFrame,
    signal_column: str,
    signal_date: Any,
    latest_signal: str,
) -> pd.DataFrame:
    try:
        validation_df = prepare_post_signal_validation_dataframe(ticker_yfinance)
        if signal_column not in validation_df.columns or pd.Timestamp(signal_date) not in validation_df.index:
            return analysis_df

        validation_signal = str(validation_df.loc[pd.Timestamp(signal_date), signal_column]).upper()
        if validation_signal != latest_signal:
            validation_df = validation_df.copy()
            validation_df.loc[pd.Timestamp(signal_date), signal_column] = latest_signal
        return validation_df
    except Exception:
        return analysis_df


def analyze_stock(user_input: str | None) -> dict[str, Any]:
    """Create a route-ready, deterministic analysis response for a stock request."""
    ticker = extract_ticker_from_text(user_input)
    if ticker is None:
        return _failure("Kode saham belum dapat dikenali dari input pengguna.")

    try:
        stock_info = get_stock_info(ticker)
    except Exception:
        return _failure("Mapping saham tidak dapat dibaca saat ini.")

    if not stock_info:
        return _failure("Kode saham belum tersedia dalam mapping sistem.")

    if not _is_research_sample(stock_info):
        return _failure("Saham valid, tetapi belum termasuk cakupan sampel evaluasi penelitian.")

    try:
        best_indicator = get_sector_best_indicator(str(stock_info["sektor"]))
        comparison = get_sector_indicator_comparison(str(stock_info["sektor"]))
        if best_indicator is None or len(comparison) != len(INDICATOR_ORDER):
            return _failure("Hasil WFA sektor belum tersedia untuk saham ini.")

        analysis_df = prepare_latest_analysis_dataframe(str(stock_info["ticker_yfinance"]))
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _failure(f"Analisis belum dapat disiapkan: {exc}")
    except Exception:
        return _failure("Analisis belum dapat disiapkan karena data teknikal tidak tersedia.")

    latest_row = analysis_df.iloc[-1]
    indicator_name = str(best_indicator["indicator"])
    signal_column = _get_signal_column(indicator_name)
    signal_date = analysis_df.index[-1]
    latest_signal = get_latest_signal_by_indicator(analysis_df, indicator_name)
    last_active_signal = get_last_active_signal(analysis_df, signal_column)
    validation_df = _build_validation_dataframe(
        str(stock_info["ticker_yfinance"]),
        analysis_df,
        signal_column,
        signal_date,
        latest_signal,
    )
    post_signal_validation = build_post_signal_validation(
        validation_df,
        signal_column,
        signal_date=signal_date,
    )
    return {
        "success": True,
        "message": "Analisis berhasil.",
        "ticker": stock_info["ticker"],
        "ticker_yfinance": stock_info["ticker_yfinance"],
        "stock_name": _stock_name(stock_info),
        "sector": stock_info["sektor"],
        "best_indicator": indicator_name,
        "latest_signal": latest_signal,
        "last_active_signal": last_active_signal,
        "latest_condition": build_latest_condition(analysis_df, indicator_name),
        "latest_date": pd.Timestamp(analysis_df.index[-1]).strftime("%Y-%m-%d"),
        "latest_close": _json_value(latest_row.get("Close")),
        "metrics": {
            "directional_accuracy": best_indicator["directional_accuracy"],
            "hit_rate": best_indicator["hit_rate"],
            "total_active_signals": best_indicator["total_active_signals"],
            "correct_signals": best_indicator["correct_signals"],
        },
        "indicator_comparison": comparison,
        "technical_hint": get_indicator_hint(indicator_name),
        "chart_data": build_chart_data(analysis_df),
        "post_signal_validation": post_signal_validation,
        "wfa_config": WFA_CONFIG.copy(),
        "data_period": DATA_PERIOD.copy(),
        "disclaimer": DISCLAIMER,
    }


def analyze_ticker(ticker: str) -> dict[str, Any]:
    """Analyze a direct ticker value using the same workflow as user text."""
    return analyze_stock(ticker)


def _find_sector_row(df: pd.DataFrame, sector_name: str) -> pd.Series | None:
    if not sector_name or "sektor" not in df.columns:
        return None
    rows = df[
        df["sektor"].astype(str).str.strip().str.casefold()
        == str(sector_name).strip().casefold()
    ]
    return None if rows.empty else rows.iloc[0]


def _record(row: pd.Series, columns: list[str], sector_key: str | None = None) -> dict[str, Any]:
    result = {}
    for column in columns:
        key = sector_key if column == "sektor" and sector_key else column
        result[key] = _json_value(row.get(column))
    return result


def _normalize_indicator_name(indicator_name: str) -> str:
    name = str(indicator_name).strip().casefold()
    aliases = {"ma crossover": "MA Crossover", "macd": "MACD", "rsi": "RSI"}
    if name not in aliases:
        raise ValueError("Indikator tidak dikenali.")
    return aliases[name]


def _get_signal_column(indicator_name: str) -> str:
    return INDICATOR_SIGNAL_COLUMNS[_normalize_indicator_name(indicator_name)]


def _is_research_sample(stock_info: dict[str, Any]) -> bool:
    return (
        str(stock_info.get("is_sample", "")).strip().casefold() == "ya"
        and str(stock_info.get("status_data", "")).strip().casefold() == "lengkap"
    )


def _stock_name(stock_info: dict[str, Any]) -> Any:
    for key in ("stock_name", "nama_saham", "nama_emiten"):
        if stock_info.get(key):
            return stock_info[key]
    return None


def _relative_position(left: Any, right: Any, left_name: str, right_name: str) -> str:
    if pd.isna(left) or pd.isna(right):
        return f"{left_name} dan {right_name} belum cukup data"
    if left > right:
        return f"{left_name} berada di atas {right_name}"
    if left < right:
        return f"{left_name} berada di bawah {right_name}"
    return f"{left_name} sama dengan {right_name}"


def _rsi_state(value: Any) -> str:
    if pd.isna(value):
        return "belum cukup data"
    if value < 30:
        return "oversold"
    if value > 70:
        return "overbought"
    return "netral"


def _rsi_signal_note(signal: str, rsi_state: str) -> str:
    if signal != "HOLD":
        return f"Sinyal {signal} muncul karena RSI keluar dari area ekstrem 30/70."
    if rsi_state == "oversold":
        return "Sinyal HOLD; RSI masih berada di area oversold dan sistem menunggu RSI naik keluar dari area tersebut."
    if rsi_state == "overbought":
        return "Sinyal HOLD; RSI masih berada di area overbought dan sistem menunggu RSI turun keluar dari area tersebut."
    return "Sinyal HOLD karena RSI belum membentuk kondisi keluar dari area oversold atau overbought pada data terakhir."


def _format_number(value: Any) -> str:
    json_value = _json_value(value)
    return "N/A" if json_value is None else f"{float(json_value):.2f}"


def _chart_key(column: str) -> str:
    return {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}.get(column, column)


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        value = value.item()
    return value


def _failure(message: str) -> dict[str, Any]:
    return {"success": False, "message": message}
