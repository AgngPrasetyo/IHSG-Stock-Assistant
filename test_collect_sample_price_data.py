import pandas as pd

from scripts import collect_sample_price_data as collector


def make_mapping_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["BBCA", "BBRI", "TLKM", "GOTO"],
            "ticker_yfinance": ["BBCA.JK", "BBRI.JK", "TLKM.JK", "GOTO.JK"],
            "sektor": ["Finansial", "Finansial", "Infrastruktur", "Teknologi"],
            "is_sample": ["Ya", "Ya", "Ya", "Tidak"],
            "status_data": ["Lengkap", "Lengkap", "Tidak Lengkap", "Lengkap"],
            "data_start": ["2024-10-20"] * 4,
            "data_end": ["2026-06-01"] * 4,
            "jumlah_data": [381, 381, 100, 381],
            "catatan": [""] * 4,
        }
    )


def make_price_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [102.0, 103.0, 104.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [101.0, 102.0, 103.0],
            "Volume": [1000, 1100, 1200],
        },
        index=pd.date_range("2024-10-21", periods=3, freq="D", name="Date"),
    )


def test_filter_sample_stocks_keeps_complete_status_only():
    result = collector.filter_sample_stocks(make_mapping_df())

    assert list(result["ticker"]) == ["BBCA", "BBRI"]


def test_filter_sample_stocks_applies_limit():
    result = collector.filter_sample_stocks(make_mapping_df(), limit=1)

    assert len(result) == 1
    assert result.iloc[0]["ticker"] == "BBCA"


def test_collect_report_has_required_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "load_mapping", make_mapping_df)
    monkeypatch.setattr(
        collector,
        "load_or_fetch_price_data",
        lambda *args, **kwargs: make_price_df(),
    )

    report_df = collector.collect_sample_price_data(
        limit=1,
        report_path=tmp_path / "price_fetch_report.csv",
    )

    assert list(report_df.columns) == collector.REPORT_COLUMNS


def test_collect_report_success_when_dummy_data_loads(monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "load_mapping", make_mapping_df)
    monkeypatch.setattr(
        collector,
        "load_or_fetch_price_data",
        lambda *args, **kwargs: make_price_df(),
    )

    report_df = collector.collect_sample_price_data(
        limit=1,
        report_path=tmp_path / "price_fetch_report.csv",
    )

    assert report_df.iloc[0]["status_fetch"] == "SUCCESS"
    assert report_df.iloc[0]["jumlah_data"] == 3
    assert bool(report_df.iloc[0]["kolom_ohlcv_lengkap"]) is True


def test_collect_report_failed_when_fetch_raises(monkeypatch, tmp_path):
    def fail_fetch(*args, **kwargs):
        raise ValueError("network disabled in test")

    monkeypatch.setattr(collector, "load_mapping", make_mapping_df)
    monkeypatch.setattr(collector, "load_or_fetch_price_data", fail_fetch)

    report_df = collector.collect_sample_price_data(
        limit=1,
        report_path=tmp_path / "price_fetch_report.csv",
    )

    assert report_df.iloc[0]["status_fetch"] == "FAILED"
    assert "network disabled in test" in report_df.iloc[0]["error_message"]


def test_report_csv_can_be_created(monkeypatch, tmp_path):
    report_path = tmp_path / "data" / "price_fetch_report.csv"
    monkeypatch.setattr(collector, "load_mapping", make_mapping_df)
    monkeypatch.setattr(
        collector,
        "load_or_fetch_price_data",
        lambda *args, **kwargs: make_price_df(),
    )

    collector.collect_sample_price_data(limit=1, report_path=report_path)

    assert report_path.exists()
    loaded_report = pd.read_csv(report_path)
    assert list(loaded_report.columns) == collector.REPORT_COLUMNS


def test_collect_uses_mocked_fetch_and_does_not_require_internet(monkeypatch, tmp_path):
    calls = []

    def fake_fetch(ticker_yfinance, start_date, end_date, use_cache):
        calls.append(
            {
                "ticker_yfinance": ticker_yfinance,
                "start_date": start_date,
                "end_date": end_date,
                "use_cache": use_cache,
            }
        )
        return make_price_df()

    monkeypatch.setattr(collector, "load_mapping", make_mapping_df)
    monkeypatch.setattr(collector, "load_or_fetch_price_data", fake_fetch)

    report_df = collector.collect_sample_price_data(
        refresh=True,
        limit=2,
        report_path=tmp_path / "price_fetch_report.csv",
    )

    assert len(calls) == 2
    assert calls[0]["ticker_yfinance"] == "BBCA.JK"
    assert calls[0]["use_cache"] is False
    assert set(report_df["status_fetch"]) == {"SUCCESS"}
