import json
from pathlib import Path

import pytest

from services import llm_service
from services.analysis_service import analyze_stock
from services.llm_service import (
    _contains_forbidden_recommendation_terms,
    _contains_internal_field_terms,
    _get_max_output_tokens,
    _safe_float_format,
    build_llm_context,
    build_llm_prompt,
    explain_stock_analysis,
    generate_deterministic_explanation,
    generate_llm_explanation,
)


@pytest.fixture(scope="module")
def bbca_analysis():
    return analyze_stock("Analisis saham BBCA")


def test_build_llm_context_excludes_chart_data(bbca_analysis):
    context = build_llm_context(bbca_analysis)
    assert context["ticker"] == "BBCA"
    assert "chart_data" not in context
    json.dumps(context)


def test_build_llm_prompt_contains_guardrails(bbca_analysis):
    prompt = build_llm_prompt(build_llm_context(bbca_analysis)).lower()
    assert "jangan mengubah sinyal" in prompt
    assert "jangan mengubah" in prompt and "metrik" in prompt
    assert "jangan memberi rekomendasi investasi final" in prompt


def test_deterministic_explanation_valid_bbca(bbca_analysis):
    explanation = generate_deterministic_explanation(bbca_analysis)
    assert "BBCA" in explanation
    assert "Finansial" in explanation
    assert "MA Crossover" in explanation
    assert bbca_analysis["latest_signal"] in explanation
    assert "bantuan analisis teknikal" in explanation.lower()


def test_deterministic_explanation_preserves_metrics(bbca_analysis):
    explanation = generate_deterministic_explanation(bbca_analysis)
    metrics = bbca_analysis["metrics"]
    assert f"{float(metrics['directional_accuracy']):.2f}%" in explanation
    assert _safe_float_format(metrics["total_active_signals"], 0) in explanation
    assert _safe_float_format(metrics["correct_signals"], 0) in explanation


def test_generate_llm_explanation_fallback_when_api_disabled(monkeypatch, bbca_analysis):
    monkeypatch.setenv("LLM_ENABLE_API", "false")
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is True
    assert result["provider"] == "deterministic"


def test_generate_llm_explanation_fallback_when_api_key_missing(monkeypatch, bbca_analysis):
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is True
    assert result["provider"] == "deterministic"


def test_explain_stock_analysis_valid(monkeypatch):
    monkeypatch.setenv("LLM_ENABLE_API", "false")
    result = explain_stock_analysis("Analisis saham BBCA")
    assert result["success"] is True
    assert result["analysis"]["success"] is True
    assert result["explanation"]


def test_explain_stock_analysis_invalid_ticker(monkeypatch):
    monkeypatch.setenv("LLM_ENABLE_API", "false")
    result = explain_stock_analysis("Analisis saham ABCDXYZ")
    assert result["success"] is False
    assert "kode saham" in result["explanation"].lower()


def test_no_forbidden_recommendation_terms_in_fallback(bbca_analysis):
    explanation = generate_deterministic_explanation(bbca_analysis)
    assert _contains_forbidden_recommendation_terms(explanation) is False


def test_openai_call_is_mocked(monkeypatch, bbca_analysis):
    calls = {}

    class FakeResponse:
        output_text = "BBCA memiliki sinyal HOLD. Hasil ini adalah bantuan analisis teknikal dan bukan rekomendasi investasi final."

    class FakeResponses:
        def create(self, **kwargs):
            calls.update(kwargs)
            return FakeResponse()

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-mini")
    monkeypatch.setattr(llm_service, "OpenAI", FakeClient)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is False
    assert result["provider"] == "openai"
    assert result["fallback_reason"] is None
    assert calls["model"] == "gpt-5.4-mini"
    assert calls["max_output_tokens"] == 700
    assert '"chart_data"' not in calls["input"]


def test_llm_service_does_not_import_web_tools():
    source = Path("services/llm_service.py").read_text(encoding="utf-8").lower()
    assert "web_search" not in source
    assert "file_search" not in source
    assert "tools=" not in source



def test_safe_disclaimer_not_forbidden():
    assert _contains_forbidden_recommendation_terms("Hasil ini bukan rekomendasi investasi final.") is False


def test_forbidden_wajib_beli_detected():
    assert _contains_forbidden_recommendation_terms("Saham ini wajib beli.") is True


def test_forbidden_pasti_naik_detected():
    assert _contains_forbidden_recommendation_terms("Harga pasti naik.") is True


def test_forbidden_final_recommendation_detected():
    assert _contains_forbidden_recommendation_terms("Ini adalah rekomendasi investasi final.") is True


def test_openai_mock_with_safe_disclaimer_does_not_fallback(monkeypatch, bbca_analysis):
    class FakeResponse:
        output_text = "BBCA memiliki sinyal HOLD. Hasil ini adalah bantuan analisis teknikal dan bukan rekomendasi investasi final."

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: FakeResponse()})()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", FakeClient)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is False
    assert result["fallback_reason"] is None


def test_generate_llm_explanation_reports_api_disabled_reason(monkeypatch, bbca_analysis):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "false")
    result = generate_llm_explanation(bbca_analysis)
    assert result["fallback_reason"] == "api_disabled"


def test_generate_llm_explanation_reports_provider_not_openai_reason(monkeypatch, bbca_analysis):
    monkeypatch.setenv("LLM_PROVIDER", "deterministic")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "provider_not_openai"


def test_generate_llm_explanation_reports_api_error_reason(monkeypatch, bbca_analysis):
    class FailingClient:
        def __init__(self, **kwargs):
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("mock failure"))})()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", FailingClient)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "api_error:RuntimeError:mock failure"




def test_default_max_output_tokens_is_700(monkeypatch):
    monkeypatch.delenv("OPENAI_MAX_OUTPUT_TOKENS", raising=False)
    assert _get_max_output_tokens() == 700


def test_invalid_max_output_tokens_falls_back_to_700(monkeypatch):
    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "not-a-number")
    assert _get_max_output_tokens() == 700




def test_build_llm_context_adds_two_decimal_formatted_metrics(bbca_analysis):
    context = build_llm_context(bbca_analysis)
    assert f"{float(bbca_analysis['metrics']['directional_accuracy']):.2f}%" in context["metrik_evaluasi"]
    assert f"{float(bbca_analysis['metrics']['hit_rate']):.2f}%" in context["metrik_evaluasi"]
    assert str(int(bbca_analysis["metrics"]["total_active_signals"])) in context["metrik_evaluasi"]


def test_fallback_explanation_formats_percentages_to_two_decimals(bbca_analysis):
    explanation = generate_deterministic_explanation(bbca_analysis)
    assert f"{float(bbca_analysis['metrics']['directional_accuracy']):.2f}%" in explanation
    assert "54.83870967741935%" not in explanation


def test_prompt_contains_correct_hold_and_horizon_guidance(bbca_analysis):
    prompt = build_llm_prompt(build_llm_context(bbca_analysis))
    assert "Jika sinyal teknikal saat ini adalah HOLD" in prompt
    assert "Jika latest_signal adalah HOLD" not in prompt
    assert "latest_signal" in prompt
    assert "belum ada sinyal BUY atau SELL aktif pada tanggal terakhir" in prompt
    assert "Jangan menyimpulkan HOLD hanya dari posisi harga terhadap SMA" in prompt
    assert "crossover SMA20 dan SMA50" in prompt
    assert "Hit Rate adalah rata-rata keberhasilan sinyal aktif per window evaluasi" in prompt
    assert "oversold tidak otomatis BUY" in prompt
    assert "horizon evaluasi 3 trading days" in prompt
    assert "teks biasa tanpa markdown bold" in prompt



def test_prompt_forbids_internal_field_terms(bbca_analysis):
    prompt = build_llm_prompt(build_llm_context(bbca_analysis))
    assert "Jangan pernah menyebut nama field internal" in prompt
    assert "formatted_metrics" in prompt
    assert "latest_condition" in prompt


def test_deterministic_explanation_no_internal_terms(bbca_analysis):
    explanation = generate_deterministic_explanation(bbca_analysis)
    assert _contains_internal_field_terms(explanation) is False


def test_openai_output_with_internal_terms_falls_back(monkeypatch, bbca_analysis):
    class FakeResponse:
        output_text = "Berdasarkan formatted_metrics dan latest_condition, BBCA memiliki sinyal HOLD."

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: FakeResponse()})()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", FakeClient)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "internal_terms_in_output"
    assert result["provider"] == "deterministic"


def test_openai_output_natural_language_success(monkeypatch, bbca_analysis):
    class FakeResponse:
        output_text = "Berdasarkan metrik evaluasi dan kondisi teknikal terbaru, BBCA memiliki sinyal HOLD. Hasil ini adalah bantuan analisis teknikal dan bukan rekomendasi investasi final."

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: FakeResponse()})()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", FakeClient)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is False
    assert result["provider"] == "openai"


def test_explain_stock_analysis_output_no_internal_terms_in_fallback(monkeypatch):
    monkeypatch.setenv("LLM_ENABLE_API", "false")
    result = explain_stock_analysis("Analisis saham BBCA")
    assert _contains_internal_field_terms(result["explanation"]) is False





def test_build_llm_context_is_compact(bbca_analysis):
    context = build_llm_context(bbca_analysis)
    for key in ("metrics", "indicator_comparison", "wfa_config", "data_period", "chart_data"):
        assert key not in context
    assert "stock_name" not in context


def test_build_llm_context_uses_natural_keys(bbca_analysis):
    context = build_llm_context(bbca_analysis)
    assert {"metrik_evaluasi", "perbandingan_indikator", "konfigurasi_evaluasi", "periode_data"}.issubset(context)


def test_build_llm_prompt_not_too_large(bbca_analysis):
    prompt = build_llm_prompt(build_llm_context(bbca_analysis))
    assert len(prompt.split()) < 850


def test_prompt_still_contains_guardrails(bbca_analysis):
    prompt = build_llm_prompt(build_llm_context(bbca_analysis)).lower()
    assert "jangan mengubah sinyal" in prompt
    assert "jangan menghitung ulang indikator" in prompt
    assert "jangan memberi rekomendasi investasi final" in prompt
    assert "crossover sma20 dan sma50" in prompt


def test_openai_mock_still_receives_no_chart_data(monkeypatch, bbca_analysis):
    calls = {}

    class FakeResponse:
        output_text = "BBCA memiliki sinyal HOLD. Hasil ini adalah bantuan analisis teknikal dan bukan rekomendasi investasi final."

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: (calls.update(kwargs), FakeResponse())[1]})()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", FakeClient)
    generate_llm_explanation(bbca_analysis)
    assert '"chart_data"' not in calls["input"]


def test_output_still_no_internal_terms(bbca_analysis):
    assert _contains_internal_field_terms(generate_deterministic_explanation(bbca_analysis)) is False


def test_generate_llm_explanation_still_success_with_mock(monkeypatch, bbca_analysis):
    class FakeResponse:
        output_text = "BBCA memiliki sinyal HOLD. Hasil ini adalah bantuan analisis teknikal dan bukan rekomendasi investasi final."

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: FakeResponse()})()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", FakeClient)
    result = generate_llm_explanation(bbca_analysis)
    assert result["used_fallback"] is False
    assert result["provider"] == "openai"




def test_invalid_analysis_does_not_call_openai(monkeypatch):
    class UnexpectedOpenAI:
        def __init__(self, **_kwargs):
            raise AssertionError("OpenAI must not be created for failed analysis")

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", UnexpectedOpenAI)

    result = generate_llm_explanation({
        "success": False,
        "message": "Kode saham belum tersedia dalam mapping sistem.",
    })

    assert result["success"] is False
    assert result["provider"] == "deterministic"
    assert result["model"] == "deterministic"
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "analysis_failed"
    assert result["explanation"]


def test_explain_stock_analysis_invalid_uses_deterministic_fallback(monkeypatch):
    class UnexpectedOpenAI:
        def __init__(self, **_kwargs):
            raise AssertionError("OpenAI must not be created for failed analysis")

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_ENABLE_API", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_service, "OpenAI", UnexpectedOpenAI)

    result = explain_stock_analysis("Analisis saham ABCDXYZ")

    assert result["success"] is False
    assert result["llm"]["provider"] == "deterministic"
    assert result["llm"]["used_fallback"] is True
    assert result["llm"]["fallback_reason"] == "analysis_failed"
    assert result["explanation"]
