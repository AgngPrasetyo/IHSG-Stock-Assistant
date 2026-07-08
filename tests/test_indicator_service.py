import pandas as pd

from services.indicator_service import (
    calculate_all_indicators,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)

INDICATOR_COLUMNS = [
    "SMA10",
    "SMA50",
    "Volume_MA20",
    "EMA12",
    "EMA26",
    "MACD",
    "MACD_Signal",
    "MACD_Histogram",
    "RSI",
]


def make_dummy_ohlcv() -> pd.DataFrame:
    dates = pd.date_range("2024-10-21", periods=80, freq="D", name="Date")
    close = [100 + index * 0.5 + (index % 5 - 2) for index in range(80)]
    return pd.DataFrame(
        {
            "Open": [x - 0.5 for x in close],
            "High": [x + 1 for x in close],
            "Low": [x - 1 for x in close],
            "Close": close,
            "Volume": [1000 + i for i in range(80)],
        },
        index=dates,
    )


def test_calculate_sma_returns_series_with_same_length():
    result = calculate_sma(make_dummy_ohlcv(), 10)

    assert isinstance(result, pd.Series)
    assert len(result) == 80


def test_calculate_macd_adds_macd_columns():
    result = calculate_macd(make_dummy_ohlcv())

    assert {"EMA12", "EMA26", "MACD", "MACD_Signal", "MACD_Histogram"}.issubset(result.columns)


def test_calculate_rsi_adds_rsi_column():
    assert "RSI" in calculate_rsi(make_dummy_ohlcv()).columns


def test_calculate_all_indicators_adds_final_indicator_columns():
    result = calculate_all_indicators(make_dummy_ohlcv())

    assert set(INDICATOR_COLUMNS).issubset(result.columns)
    assert "SMA20" not in result.columns
    assert "EMA20" not in result.columns
    assert "EMA50" not in result.columns


def test_indicator_functions_do_not_modify_original_dataframe():
    df = make_dummy_ohlcv()
    original = df.copy(deep=True)

    calculate_all_indicators(df)

    pd.testing.assert_frame_equal(df, original)


def test_output_index_is_sorted_by_date():
    result = calculate_all_indicators(make_dummy_ohlcv().sort_index(ascending=False))

    assert result.index.is_monotonic_increasing
