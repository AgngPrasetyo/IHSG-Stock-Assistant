import pandas as pd

from services.signal_service import (
    MA_CROSSOVER_SIGNAL_COLUMN,
    MA_SIGNAL_COLUMN,
    generate_all_signals,
    generate_ma_signal,
    generate_macd_signal,
    generate_rsi_signal,
    get_latest_signal,
)


def make_dummy_ohlcv() -> pd.DataFrame:
    dates = pd.date_range("2024-10-21", periods=80, freq="D", name="Date")
    close_prices = [100 + (index * 0.5) + ((index % 5) - 2) for index in range(80)]
    return pd.DataFrame(
        {"Open": close_prices, "High": [price + 1 for price in close_prices], "Low": [price - 1 for price in close_prices], "Close": close_prices, "Volume": [1000] * 80}, index=dates
    )


def make_signal_base(values: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(values, index=pd.date_range("2024-10-21", periods=len(next(iter(values.values()))), freq="D", name="Date"))


def test_generate_ma_signal_uses_sma20_sma50_crossover():
    result = generate_ma_signal(make_dummy_ohlcv())
    assert MA_CROSSOVER_SIGNAL_COLUMN in result.columns
    assert MA_SIGNAL_COLUMN == MA_CROSSOVER_SIGNAL_COLUMN
    assert {"SMA20", "SMA50"}.issubset(result.columns)


def test_generate_ma_signal_buy_when_sma20_crosses_above_sma50():
    df = make_signal_base({"Close": [10.0, 11.0], "SMA20": [10.0, 11.0], "SMA50": [10.0, 10.0]})
    assert generate_ma_signal(df)[MA_CROSSOVER_SIGNAL_COLUMN].iloc[-1] == "BUY"


def test_generate_ma_signal_sell_when_sma20_crosses_below_sma50():
    df = make_signal_base({"Close": [10.0, 9.0], "SMA20": [10.0, 9.0], "SMA50": [10.0, 10.0]})
    assert generate_ma_signal(df)[MA_CROSSOVER_SIGNAL_COLUMN].iloc[-1] == "SELL"


def test_generate_macd_signal_uses_sma50_filter():
    buy = make_signal_base({"Close": [11.0, 11.0], "SMA50": [10.0, 10.0], "MACD": [-0.2, 0.2], "MACD_Signal": [0.0, 0.0]})
    blocked = buy.assign(SMA50=[12.0, 12.0])
    assert generate_macd_signal(buy)["MACD_Trade_Signal"].iloc[-1] == "BUY"
    assert generate_macd_signal(blocked)["MACD_Trade_Signal"].iloc[-1] == "HOLD"


def test_generate_rsi_signal_uses_sma50_filter():
    buy = make_signal_base({"Close": [31.0, 31.0], "SMA50": [30.0, 30.0], "RSI": [29.0, 30.0]})
    blocked = buy.assign(SMA50=[32.0, 32.0])
    assert generate_rsi_signal(buy)["RSI_Signal"].iloc[-1] == "BUY"
    assert generate_rsi_signal(blocked)["RSI_Signal"].iloc[-1] == "HOLD"


def test_get_latest_signal_ma_crossover_returns_ma_crossover():
    df = make_signal_base({"Close": [10.0, 11.0], "SMA20": [10.0, 11.0], "SMA50": [10.0, 10.0]})
    result = get_latest_signal(df, "sma20/sma50")
    assert result["indicator"] == "MA Crossover"
    assert result["signal"] == "BUY"


def test_reason_mentions_sma50_not_ema50():
    df = make_signal_base({"Close": [11.0, 11.0], "SMA50": [10.0, 10.0], "MACD": [-0.2, 0.2], "MACD_Signal": [0.0, 0.0]})
    reason = get_latest_signal(df, "MACD")["reason"]
    assert "SMA50" in reason
    assert "EMA50" not in reason


def test_generate_all_signals_outputs_ma_crossover_macd_rsi_columns():
    result = generate_all_signals(make_dummy_ohlcv())
    assert {MA_CROSSOVER_SIGNAL_COLUMN, "MACD_Trade_Signal", "RSI_Signal"}.issubset(result.columns)
    assert "EMA20_Signal" not in result.columns


def test_signal_functions_do_not_modify_original_dataframe():
    df = make_dummy_ohlcv()
    original_df = df.copy(deep=True)
    generate_all_signals(df)
    pd.testing.assert_frame_equal(df, original_df)
