import json
from pathlib import Path

import pandas as pd
import pytest

import services.analysis_service as analysis_service
from services.analysis_service import WFA_CONFIG, analyze_stock
from services.signal_service import (
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)


@pytest.fixture(scope="module")
def bbca_result():
    return analyze_stock("Analisis saham BBCA")


def test_analyze_stock_valid_bbca_success(bbca_result):
    assert bbca_result["success"] is True
    assert bbca_result["ticker"] == "BBCA"
    assert bbca_result["sector"] == "Finansial"
    assert bbca_result["best_indicator"] == "MACD"
    assert bbca_result["latest_signal"] in {"BUY", "SELL", "HOLD"}
    assert bbca_result["metrics"]
    assert len(bbca_result["indicator_comparison"]) == 3
    assert bbca_result["chart_data"]
    assert bbca_result["disclaimer"]


def test_analyze_stock_valid_energy_uses_final_best_indicator():
    result = analyze_stock("Tolong cek ADMR")

    assert result["success"] is True
    assert result["sector"] == "Energi"
    assert result["best_indicator"] == "MA Crossover"


def test_analyze_stock_unknown_ticker():
    result = analyze_stock("Analisis saham ABCDXYZ")
    assert result["success"] is False


def test_analyze_stock_empty_input():
    result = analyze_stock("")
    assert result["success"] is False


def test_indicator_comparison_contains_three_indicators(bbca_result):
    assert {item["indicator"] for item in bbca_result["indicator_comparison"]} == {"MA Crossover", "MACD", "RSI"}


def test_analysis_response_includes_final_metric_hints(bbca_result):
    metric_items = bbca_result["technical_hint"].get("metric_items")

    assert metric_items
    assert {item["term"] for item in metric_items} == {
        "Directional Accuracy",
        "Average Forward Return",
        "Hit Rate",
        "Total Active Signals",
        "Correct Signals",
    }


def test_analysis_response_includes_post_signal_validation(bbca_result):
    assert "post_signal_validation" in bbca_result
    assert isinstance(bbca_result["post_signal_validation"], list)
    assert [item["label"] for item in bbca_result["post_signal_validation"]] == ["T+1", "T+3", "T+5", "T+10"]
    for item in bbca_result["post_signal_validation"]:
        assert {"horizon", "label", "status", "message"}.issubset(item)


def test_post_signal_validation_data_does_not_change_latest_signal_or_date(monkeypatch):
    analysis_df = _make_analysis_df(
        ["2026-06-18", "2026-06-19", "2026-06-22"],
        [100.0, 101.0, 102.0],
        ["HOLD", "HOLD", "BUY"],
    )
    validation_df = _make_analysis_df(
        [
            "2026-06-18",
            "2026-06-19",
            "2026-06-22",
            "2026-06-23",
            "2026-06-24",
            "2026-06-25",
            "2026-06-26",
            "2026-06-27",
        ],
        [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
        ["HOLD", "HOLD", "SELL", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD"],
    )

    monkeypatch.setattr(analysis_service, "prepare_latest_analysis_dataframe", lambda ticker: analysis_df)
    monkeypatch.setattr(analysis_service, "prepare_post_signal_validation_dataframe", lambda ticker: validation_df)

    result = analyze_stock("Analisis saham BBCA")

    assert result["success"] is True
    assert result["latest_date"] == "2026-06-22"
    assert result["latest_signal"] == "BUY"
    assert [item["target_date"] for item in result["post_signal_validation"]] == [
        "2026-06-23",
        "2026-06-25",
        "2026-06-27",
        None,
    ]
    assert [item["status"] for item in result["post_signal_validation"]] == [
        "MATCH",
        "MATCH",
        "MATCH",
        "UNAVAILABLE",
    ]


def test_post_signal_validation_falls_back_to_main_dataframe(monkeypatch):
    analysis_df = _make_analysis_df(
        ["2026-06-18", "2026-06-19", "2026-06-22"],
        [100.0, 101.0, 102.0],
        ["HOLD", "HOLD", "BUY"],
    )

    def raise_validation_error(ticker):
        raise ValueError("validation data unavailable")

    monkeypatch.setattr(analysis_service, "prepare_latest_analysis_dataframe", lambda ticker: analysis_df)
    monkeypatch.setattr(analysis_service, "prepare_post_signal_validation_dataframe", raise_validation_error)

    result = analyze_stock("Analisis saham BBCA")

    assert result["success"] is True
    assert isinstance(result["post_signal_validation"], list)
    assert [item["status"] for item in result["post_signal_validation"]] == [
        "UNAVAILABLE",
        "UNAVAILABLE",
        "UNAVAILABLE",
        "UNAVAILABLE",
    ]


def test_wfa_config_in_response(bbca_result):
    assert bbca_result["wfa_config"] == WFA_CONFIG
    assert bbca_result["wfa_config"]["evaluation_method"] == "Average Forward Return"
    assert bbca_result["wfa_config"]["evaluation_horizons"] == [1, 3, 5, 10]
    assert bbca_result["wfa_config"]["evaluation_horizon_label"] == "T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham"


def test_disclaimer_no_recommendation_wording(bbca_result):
    assert "bukan rekomendasi investasi final" in bbca_result["disclaimer"]


def test_chart_data_json_serializable(bbca_result):
    assert json.loads(json.dumps(bbca_result["chart_data"]))


def test_analysis_service_does_not_call_llm():
    source = Path("services/analysis_service.py").read_text(encoding="utf-8").lower()

    assert "import openai" not in source
    assert "openai.api" not in source


def _make_analysis_df(dates, closes, signals):
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [close + 1 for close in closes],
            "Low": [close - 1 for close in closes],
            "Close": closes,
            "Volume": [1000] * len(closes),
            "SMA10": [close + 1 for close in closes],
            "SMA50": closes,
            "MACD": [0.0] * len(closes),
            "MACD_Signal": [0.0] * len(closes),
            "RSI": [50.0] * len(closes),
            MA_CROSSOVER_SIGNAL_COLUMN: signals,
            MACD_TRADE_SIGNAL_COLUMN: signals,
            RSI_SIGNAL_COLUMN: signals,
        },
        index=pd.DatetimeIndex(pd.to_datetime(dates), name="Date"),
    )
