import json
from pathlib import Path

import pytest

from services.analysis_service import analyze_stock


@pytest.fixture(scope="module")
def bbca_result():
    return analyze_stock("Analisis saham BBCA")


def test_analyze_stock_valid_bbca_success(bbca_result):
    assert bbca_result["success"] is True
    assert bbca_result["ticker"] == "BBCA"
    assert bbca_result["sector"] == "Finansial"
    assert bbca_result["best_indicator"] == "MA Crossover"
    assert bbca_result["latest_signal"] in {"BUY", "SELL", "HOLD"}
    assert bbca_result["metrics"]
    assert len(bbca_result["indicator_comparison"]) == 3
    assert bbca_result["chart_data"]
    assert bbca_result["disclaimer"]


def test_analyze_stock_valid_energy_uses_rsi():
    result = analyze_stock("Tolong cek ADMR")
    assert result["success"] is True
    assert result["sector"] == "Energi"
    assert result["best_indicator"] == "RSI"


def test_analyze_stock_unknown_ticker():
    result = analyze_stock("Analisis saham ABCDXYZ")
    assert result["success"] is False


def test_analyze_stock_empty_input():
    result = analyze_stock("")
    assert result["success"] is False


def test_indicator_comparison_contains_three_indicators(bbca_result):
    assert {item["indicator"] for item in bbca_result["indicator_comparison"]} == {
        "MA Crossover", "MACD", "RSI"
    }




def test_analysis_response_includes_metric_hints(bbca_result):
    metric_items = bbca_result["technical_hint"].get("metric_items")

    assert metric_items
    assert {item["term"] for item in metric_items} == {
        "Directional Accuracy", "Hit Rate", "Total Active Signals", "Correct Signals"
    }

def test_wfa_config_in_response(bbca_result):
    assert bbca_result["wfa_config"] == {
        "in_sample_months": 6,
        "out_sample_months": 3,
        "shift_months": 3,
        "evaluation_horizon_periods": 3,
    }


def test_disclaimer_no_recommendation_wording(bbca_result):
    assert "bukan rekomendasi investasi final" in bbca_result["disclaimer"]


def test_chart_data_json_serializable(bbca_result):
    assert json.loads(json.dumps(bbca_result["chart_data"]))


def test_analysis_service_does_not_call_llm():
    source = Path("services/analysis_service.py").read_text(encoding="utf-8").lower()
    assert "import openai" not in source
    assert "openai.api" not in source
