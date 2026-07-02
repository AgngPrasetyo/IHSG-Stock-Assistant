import pandas as pd

from services.post_signal_validation_service import build_post_signal_validation


SIGNAL_COLUMN = "Signal"


def make_df(closes, signals=None, dates=None):
    if dates is None:
        dates = pd.to_datetime([
            "2026-01-02",
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
            "2026-01-09",
        ])
    if signals is None:
        signals = ["HOLD"] * len(closes)
    return pd.DataFrame(
        {"Close": closes, SIGNAL_COLUMN: signals},
        index=pd.DatetimeIndex(dates[: len(closes)], name="Date"),
    )


def test_buy_match_t1_when_future_close_higher():
    result = build_post_signal_validation(
        make_df([100, 105], ["BUY", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["status"] == "MATCH"
    assert result[0]["actual_direction"] == "UP"


def test_buy_not_match_t1_when_future_close_lower():
    result = build_post_signal_validation(
        make_df([100, 95], ["BUY", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["status"] == "NOT_MATCH"
    assert result[0]["actual_direction"] == "DOWN"


def test_sell_match_t1_when_future_close_lower():
    result = build_post_signal_validation(
        make_df([100, 95], ["SELL", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["status"] == "MATCH"
    assert result[0]["actual_direction"] == "DOWN"


def test_sell_not_match_t1_when_future_close_higher():
    result = build_post_signal_validation(
        make_df([100, 105], ["SELL", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["status"] == "NOT_MATCH"
    assert result[0]["actual_direction"] == "UP"


def test_hold_returns_not_evaluated_hold():
    result = build_post_signal_validation(
        make_df([100, 105], ["HOLD", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["status"] == "NOT_EVALUATED_HOLD"
    assert "bukan sinyal aktif" in result[0]["message"]


def test_unavailable_when_horizon_exceeds_available_rows():
    result = build_post_signal_validation(
        make_df([100, 105], ["BUY", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[3],
    )

    assert result[0]["status"] == "UNAVAILABLE"
    assert result[0]["target_date"] is None
    assert "belum tersedia" in result[0]["message"]


def test_t3_and_t5_use_row_position_not_calendar_days():
    dates = pd.to_datetime([
        "2026-01-02",
        "2026-01-05",
        "2026-01-08",
        "2026-01-20",
        "2026-01-21",
        "2026-02-02",
    ])
    result = build_post_signal_validation(
        make_df([100, 101, 102, 103, 104, 105], ["BUY", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD"], dates),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[3, 5],
    )

    assert result[0]["target_date"] == "2026-01-20"
    assert result[1]["target_date"] == "2026-02-02"


def test_return_pct_is_calculated_and_rounded():
    result = build_post_signal_validation(
        make_df([123.45, 130.12], ["BUY", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["return_pct"] == 5.403


def test_signal_date_missing_returns_unavailable_for_all_horizons():
    result = build_post_signal_validation(
        make_df([100, 105], ["BUY", "HOLD"]),
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-02-02"),
        horizons=[1, 3, 5],
    )

    assert [item["status"] for item in result] == ["UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE"]


def test_dataframe_is_sorted_before_validation():
    df = make_df([105, 100], ["HOLD", "BUY"], dates=pd.to_datetime(["2026-01-05", "2026-01-02"]))
    result = build_post_signal_validation(
        df,
        SIGNAL_COLUMN,
        signal_date=pd.Timestamp("2026-01-02"),
        horizons=[1],
    )

    assert result[0]["target_date"] == "2026-01-05"
    assert result[0]["status"] == "MATCH"
