import pandas as pd
import pytest

from services import data_service
from services.data_service import (
    END_DATE,
    START_DATE,
    fetch_price_data,
    get_cache_path,
    load_cached_price_data,
    load_or_fetch_price_data,
    save_price_cache,
    validate_ohlcv,
)


def make_dummy_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 102.0, 101.0],
            "High": [103.0, 104.0, 102.0],
            "Low": [99.0, 100.0, 98.0],
            "Close": [102.0, 101.0, 100.0],
            "Volume": [1000, 1200, 900],
        },
        index=pd.date_range("2024-10-21", periods=3, freq="D", name="Date"),
    )


def test_validate_ohlcv_success():
    assert validate_ohlcv(make_dummy_ohlcv()) is True


def test_validate_ohlcv_fails_when_close_missing():
    df = make_dummy_ohlcv().drop(columns=["Close"])

    with pytest.raises(ValueError, match="Close"):
        validate_ohlcv(df)


def test_get_cache_path_uses_current_prices_folder_and_date_range():
    cache_path = get_cache_path("BBCA.JK")

    assert cache_path.parent.name == "prices"
    assert cache_path.parent.parent.name == "cache"
    assert cache_path.name == f"BBCA_JK_{START_DATE}_{END_DATE}.csv"


def test_save_and_load_cached_price_data(monkeypatch, tmp_path):
    monkeypatch.setattr(data_service, "CACHE_DIR", tmp_path / "cache" / "prices")
    dummy_df = make_dummy_ohlcv()

    cache_path = save_price_cache("BBCA.JK", dummy_df)
    loaded_df = load_cached_price_data("BBCA.JK")

    assert cache_path.exists()
    assert loaded_df is not None
    assert validate_ohlcv(loaded_df) is True
    pd.testing.assert_frame_equal(loaded_df, dummy_df, check_freq=False)


def test_load_or_fetch_price_data_uses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(data_service, "CACHE_DIR", tmp_path / "cache" / "prices")
    dummy_df = make_dummy_ohlcv()
    save_price_cache("BBCA.JK", dummy_df)

    def fail_fetch(*args, **kwargs):
        raise AssertionError("fetch_price_data tidak boleh dipanggil saat cache tersedia.")

    monkeypatch.setattr(data_service, "fetch_price_data", fail_fetch)
    loaded_df = load_or_fetch_price_data("BBCA.JK", use_cache=True)

    pd.testing.assert_frame_equal(loaded_df, dummy_df, check_freq=False)


def test_fetch_price_data_uses_ticker_history_fallback(monkeypatch, tmp_path):
    dummy_df = make_dummy_ohlcv()

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, start, end, interval, auto_adjust):
            return dummy_df.sort_index(ascending=False)

    monkeypatch.setattr(data_service, "YFINANCE_CACHE_DIR", tmp_path / "cache" / "yfinance")
    monkeypatch.setattr(data_service.yf, "download", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(data_service.yf, "Ticker", FakeTicker)

    result = fetch_price_data("BBCA.JK")

    assert validate_ohlcv(result) is True
    assert result.index.is_monotonic_increasing
    pd.testing.assert_frame_equal(result, dummy_df, check_freq=False)


def test_fetch_price_data_uses_yahoo_chart_fallback(monkeypatch, tmp_path):
    class EmptyTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, start, end, interval, auto_adjust):
            return pd.DataFrame()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            timestamps = [
                int(pd.Timestamp("2024-10-22", tz="UTC").timestamp()),
                int(pd.Timestamp("2024-10-21", tz="UTC").timestamp()),
            ]
            return {
                "chart": {
                    "result": [
                        {
                            "timestamp": timestamps,
                            "indicators": {
                                "quote": [
                                    {
                                        "open": [102.0, 100.0],
                                        "high": [104.0, 103.0],
                                        "low": [100.0, 99.0],
                                        "close": [101.0, 102.0],
                                        "volume": [1200, 1000],
                                    }
                                ]
                            },
                        }
                    ]
                }
            }

    monkeypatch.setattr(data_service, "YFINANCE_CACHE_DIR", tmp_path / "cache" / "yfinance")
    monkeypatch.setattr(data_service.yf, "download", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(data_service.yf, "Ticker", EmptyTicker)
    monkeypatch.setattr(data_service.requests, "get", lambda *args, **kwargs: FakeResponse())

    result = fetch_price_data("BBCA.JK")

    assert validate_ohlcv(result) is True
    assert result.index.is_monotonic_increasing
    assert list(result["Close"]) == [102.0, 101.0]
