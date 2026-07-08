"""Post-signal validation helpers for already-formed latest signals."""

from __future__ import annotations

from typing import Any

import pandas as pd


DEFAULT_HORIZONS = [1, 3, 5, 10]
UNAVAILABLE_MESSAGE = "Data setelah tanggal sinyal belum tersedia untuk periode evaluasi ini."


def build_post_signal_validation(
    df: pd.DataFrame,
    signal_column: str,
    signal_date: pd.Timestamp | None = None,
    horizons: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Validate an existing signal against future closes by trading-day position."""
    selected_horizons = DEFAULT_HORIZONS if horizons is None else horizons

    if df is None or df.empty:
        return [_unavailable_item(horizon, None, None, None) for horizon in selected_horizons]

    sorted_df = df.copy().sort_index()
    selected_signal_date = (
        pd.Timestamp(sorted_df.index[-1]) if signal_date is None else pd.Timestamp(signal_date)
    )
    signal_date_text = _format_date(selected_signal_date)

    if signal_column not in sorted_df.columns or "Close" not in sorted_df.columns:
        return [_unavailable_item(horizon, signal_date_text, None, None) for horizon in selected_horizons]

    if selected_signal_date not in sorted_df.index:
        return [_unavailable_item(horizon, signal_date_text, None, None) for horizon in selected_horizons]

    signal_position = _position_of(sorted_df.index, selected_signal_date)
    row = sorted_df.iloc[signal_position]
    signal = _normalize_signal(row.get(signal_column))
    close_t = _to_float(row.get("Close"))

    return [
        _build_item(sorted_df, signal_position, horizon, signal_date_text, signal, close_t)
        for horizon in selected_horizons
    ]


def _build_item(
    sorted_df: pd.DataFrame,
    signal_position: int,
    horizon: int,
    signal_date_text: str,
    signal: str,
    close_t: float | None,
) -> dict[str, Any]:
    target_position = signal_position + int(horizon)
    if target_position >= len(sorted_df):
        item = _unavailable_item(horizon, signal_date_text, signal, close_t)
        if signal == "HOLD":
            item["status"] = "NOT_EVALUATED_HOLD"
            item["message"] = "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif."
        return item

    target_date = sorted_df.index[target_position]
    close_future = _to_float(sorted_df.iloc[target_position].get("Close"))
    actual_direction = _actual_direction(close_t, close_future)
    return_pct = _return_pct(close_t, close_future)

    if signal == "HOLD":
        status = "NOT_EVALUATED_HOLD"
        message = "Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif."
    else:
        status = _status_for_signal(signal, actual_direction)
        message = _message_for_status(status, signal, horizon)

    return {
        "horizon": int(horizon),
        "label": f"T+{int(horizon)}",
        "signal_date": signal_date_text,
        "target_date": _format_date(target_date),
        "signal": signal,
        "close_t": close_t,
        "close_future": close_future,
        "actual_direction": actual_direction,
        "return_pct": return_pct,
        "status": status,
        "message": message,
    }


def _status_for_signal(signal: str, actual_direction: str | None) -> str:
    if actual_direction is None or signal not in {"BUY", "SELL"}:
        return "UNAVAILABLE"
    if actual_direction == "FLAT":
        return "NOT_MATCH_FLAT"
    if signal == "BUY":
        return "MATCH" if actual_direction == "UP" else "NOT_MATCH"
    return "MATCH" if actual_direction == "DOWN" else "NOT_MATCH"


def _message_for_status(status: str, signal: str, horizon: int) -> str:
    if status == "MATCH":
        return f"Pergerakan Close pada T+{int(horizon)} searah dengan sinyal {signal}."
    if status == "NOT_MATCH":
        return f"Pergerakan Close pada T+{int(horizon)} tidak searah dengan sinyal {signal}."
    if status == "NOT_MATCH_FLAT":
        return f"Close pada T+{int(horizon)} tidak berubah dari Close saat sinyal."
    return UNAVAILABLE_MESSAGE


def _unavailable_item(
    horizon: int,
    signal_date_text: str | None,
    signal: str | None,
    close_t: float | None,
) -> dict[str, Any]:
    return {
        "horizon": int(horizon),
        "label": f"T+{int(horizon)}",
        "signal_date": signal_date_text,
        "target_date": None,
        "signal": signal,
        "close_t": close_t,
        "close_future": None,
        "actual_direction": None,
        "return_pct": None,
        "status": "UNAVAILABLE",
        "message": UNAVAILABLE_MESSAGE,
    }


def _position_of(index: pd.Index, signal_date: pd.Timestamp) -> int:
    location = index.get_loc(signal_date)
    if isinstance(location, slice):
        return location.start
    if hasattr(location, "nonzero"):
        return int(location.nonzero()[0][0])
    return int(location)


def _normalize_signal(value: Any) -> str:
    signal = str(value).strip().upper()
    return signal if signal in {"BUY", "SELL", "HOLD"} else "HOLD"


def _actual_direction(close_t: float | None, close_future: float | None) -> str | None:
    if close_t is None or close_future is None:
        return None
    if close_future > close_t:
        return "UP"
    if close_future < close_t:
        return "DOWN"
    return "FLAT"


def _return_pct(close_t: float | None, close_future: float | None) -> float | None:
    if close_t is None or close_future is None or close_t == 0:
        return None
    return round(((close_future - close_t) / close_t) * 100, 4)


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _format_date(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")
