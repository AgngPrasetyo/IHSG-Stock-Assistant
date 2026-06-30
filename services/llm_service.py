"""Safe natural-language explanations for deterministic stock analysis results."""

from __future__ import annotations

import json
import os
from typing import Any

from services.analysis_service import analyze_stock

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised by fallback behavior
    OpenAI = None  # type: ignore[assignment]

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_OUTPUT_TOKENS = 700
FALLBACK_DISCLAIMER = "Catatan: penjelasan ini adalah bantuan analisis teknikal, bukan saran investasi."
SAFE_DISCLAIMER_PHRASES = (
    "bukan rekomendasi investasi final",
    "bukan saran investasi",
    "bukan rekomendasi untuk membeli atau menjual",
)
FORBIDDEN_RECOMMENDATION_TERMS = (
    "wajib beli",
    "wajib jual",
    "pasti naik",
    "pasti turun",
    "harus beli",
    "harus jual",
    "saya merekomendasikan beli",
    "saya merekomendasikan jual",
    "ini adalah rekomendasi investasi final",
    "rekomendasi final untuk membeli",
    "rekomendasi final untuk menjual",
)
INTERNAL_FIELD_TERMS = (
    "formatted_metrics",
    "latest_condition",
    "analysis_result",
    "indicator_comparison",
    "latest_signal",
    "best_indicator",
    "wfa_config",
    "data_period",
    "chart_data",
)
CONTEXT_FIELDS = (
    "ticker",
    "ticker_yfinance",
    "stock_name",
    "sector",
    "best_indicator",
    "latest_signal",
    "latest_condition",
    "latest_date",
    "latest_close",
    "metrics",
    "indicator_comparison",
    "wfa_config",
    "data_period",
    "disclaimer",
)


def build_llm_context(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """Return compact, natural-language context without chart data or raw objects."""
    if not analysis_result or not analysis_result.get("success"):
        return _json_safe(
            {
                "success": False,
                "pesan": (analysis_result or {}).get("message", "Analisis belum tersedia."),
                "disclaimer": FALLBACK_DISCLAIMER,
            }
        )

    context = {
        "success": True,
        "ticker": analysis_result.get("ticker"),
        "ticker_yfinance": analysis_result.get("ticker_yfinance"),
        "sektor": analysis_result.get("sector"),
        "periode_data": _format_data_period_for_prompt(analysis_result),
        "konfigurasi_evaluasi": _format_wfa_config_for_prompt(
            analysis_result.get("wfa_config") or {}
        ),
        "indikator_terbaik": analysis_result.get("best_indicator"),
        "sinyal_teknikal_saat_ini": analysis_result.get("latest_signal"),
        "kondisi_teknikal_terbaru": analysis_result.get("latest_condition"),
        "tanggal_terbaru": analysis_result.get("latest_date"),
        "harga_penutupan_terakhir": analysis_result.get("latest_close"),
        "metrik_evaluasi": _format_metrics_for_prompt(analysis_result.get("metrics") or {}),
        "perbandingan_indikator": _format_comparison_for_prompt(
            analysis_result.get("indicator_comparison") or []
        ),
        "disclaimer": analysis_result.get("disclaimer", FALLBACK_DISCLAIMER),
    }
    if analysis_result.get("stock_name") is not None:
        context["nama_saham"] = analysis_result["stock_name"]
    return _json_safe({key: value for key, value in context.items() if value is not None})


def build_llm_prompt(analysis_context: dict[str, Any]) -> str:
    """Build a strict Indonesian prompt that explains, never alters, results."""
    payload = json.dumps(analysis_context, ensure_ascii=False, indent=2)
    return f"""Anda adalah asisten penjelas hasil analisis teknikal. Anda hanya menjelaskan output sistem deterministik.

Aturan wajib:
- Jangan mengubah sinyal, indikator terbaik, atau metrik apa pun.
- Jangan menghitung ulang indikator atau hasil WFA.
- Jangan memberi rekomendasi investasi final, jangan memprediksi harga, dan jangan menyebut kepastian naik atau turun.
- Jangan mengubah angka, sinyal, atau indikator. Gunakan metrik evaluasi yang diberikan agar persentase maksimal dua desimal.
- Jangan pernah menyebut nama field internal: formatted_metrics, latest_condition, analysis_result, indicator_comparison, latest_signal, best_indicator, wfa_config, data_period, atau chart_data.
- Gunakan bahasa natural: metrik evaluasi, kondisi teknikal terbaru, perbandingan indikator, sinyal teknikal saat ini, indikator terbaik, periode data, dan konfigurasi evaluasi.
- Sertakan penegasan bahwa hasil adalah bantuan analisis teknikal, bukan rekomendasi investasi final.
- Gunakan teks biasa tanpa markdown bold. Buat jawaban ringkas dalam 3 sampai 5 paragraf, sekitar 250 sampai 450 kata. Tampilkan persentase maksimal dua desimal, lalu gunakan urutan:
  1. Ringkasan saham
  2. Sinyal teknikal saat ini
  3. Alasan teknikal
  4. Evaluasi indikator terbaik
  5. Perbandingan indikator lain
  6. Catatan risiko
- Directional Accuracy adalah akurasi gabungan seluruh sinyal aktif BUY/SELL terhadap arah harga setelah horizon evaluasi 3 trading days.
- Hit Rate adalah rata-rata keberhasilan sinyal aktif per window evaluasi, bukan selalu sama dengan Directional Accuracy.
- Jika sinyal teknikal saat ini adalah HOLD, jelaskan bahwa belum ada sinyal BUY atau SELL aktif pada tanggal terakhir berdasarkan indikator terbaik.
- Jangan menyimpulkan HOLD hanya dari posisi harga terhadap SMA.
- Untuk MA Crossover, BUY atau SELL hanya muncul saat terjadi crossover SMA20 dan SMA50 pada data terbaru; posisi SMA20 di atas/bawah SMA50 saja bukan sinyal baru.
- Untuk MACD, BUY atau SELL hanya muncul saat crossover MACD Line dan Signal Line terkonfirmasi filter tren SMA50; posisi garis saja bukan sinyal baru.
- Untuk RSI, oversold tidak otomatis BUY dan overbought tidak otomatis SELL; sistem menunggu RSI keluar dari area ekstrem dan filter tren SMA50 terpenuhi.
- Gunakan istilah “horizon evaluasi 3 trading days”, bukan “evaluation horizon 3 periods”.

Data sistem deterministik:
{payload}"""


def generate_deterministic_explanation(analysis_result: dict[str, Any]) -> str:
    """Generate the offline explanation path without any API call."""
    if not analysis_result or not analysis_result.get("success"):
        message = (analysis_result or {}).get("message", "Analisis saham belum tersedia.")
        return f"Analisis belum dapat dibuat. {message} {FALLBACK_DISCLAIMER}"

    ticker = analysis_result.get("ticker", "Saham")
    sector = analysis_result.get("sector", "tidak tersedia")
    indicator = analysis_result.get("best_indicator", "tidak tersedia")
    signal = analysis_result.get("latest_signal", "HOLD")
    metrics = analysis_result.get("metrics") or {}
    accuracy = _format_percent(metrics.get("directional_accuracy"))
    hit_rate = _format_percent(metrics.get("hit_rate"))
    active = _safe_float_format(metrics.get("total_active_signals"), 0)
    correct = _safe_float_format(metrics.get("correct_signals"), 0)
    condition = analysis_result.get("latest_condition", "Kondisi indikator terkini belum tersedia.")

    signal_sentence = (
        "Sinyal sistem saat ini adalah HOLD. Belum ada sinyal BUY/SELL aktif berdasarkan indikator terbaik."
        if signal == "HOLD"
        else f"Sinyal sistem saat ini adalah {signal}."
    )
    comparison = _format_indicator_comparison(analysis_result.get("indicator_comparison") or [])
    return (
        f"Ringkasan saham: {ticker} berada pada sektor {sector}. "
        f"Indikator terbaik sektor menurut WFA adalah {indicator}.\n\n"
        f"Sinyal teknikal saat ini: {signal_sentence} Alasan teknikal: {condition}\n\n"
        f"Evaluasi indikator terbaik: Directional Accuracy {accuracy} adalah akurasi gabungan seluruh sinyal aktif, "
        f"Hit Rate {hit_rate} adalah rata-rata keberhasilan per window, "
        f"Total Active Signals {active}, dan Correct Signals {correct}.\n\n"
        f"Perbandingan indikator lain: {comparison}\n\n"
        "Catatan risiko: sinyal dan metrik berasal dari evaluasi historis; kondisi pasar dapat berubah. "
        f"{FALLBACK_DISCLAIMER}"
    )


def generate_openai_explanation(analysis_result: dict[str, Any]) -> tuple[str, bool, str | None]:
    """Use OpenAI only when explicitly enabled; otherwise preserve fallback behavior."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().casefold() or DEFAULT_PROVIDER
    if provider != "openai":
        return generate_deterministic_explanation(analysis_result), True, "provider_not_openai"
    if not _get_env_bool("LLM_ENABLE_API", False):
        return generate_deterministic_explanation(analysis_result), True, "api_disabled"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return generate_deterministic_explanation(analysis_result), True, "missing_api_key"
    if OpenAI is None:
        return generate_deterministic_explanation(analysis_result), True, "missing_openai_package"

    try:
        timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        max_output_tokens = _get_max_output_tokens()
        client = OpenAI(api_key=api_key, timeout=timeout)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            input=build_llm_prompt(build_llm_context(analysis_result)),
            max_output_tokens=max_output_tokens,
        )
        explanation = str(getattr(response, "output_text", "")).strip()
    except Exception as exc:
        detail = str(exc).strip() or "unknown_error"
        return (
            generate_deterministic_explanation(analysis_result),
            True,
            f"api_error:{type(exc).__name__}:{detail}",
        )

    # Guardrails are checked after provider output so unsafe or leaky text falls back.
    if _contains_internal_field_terms(explanation):
        return generate_deterministic_explanation(analysis_result), True, "internal_terms_in_output"
    if not explanation or _contains_forbidden_recommendation_terms(explanation):
        return generate_deterministic_explanation(analysis_result), True, "unsafe_output"
    if "bantuan analisis teknikal" not in explanation.casefold():
        explanation = f"{explanation}\n\n{FALLBACK_DISCLAIMER}"
    return explanation, False, None


def generate_llm_explanation(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """Return a provider-labelled explanation while preserving analysis success."""
    success = bool((analysis_result or {}).get("success", False))
    if not success:
        explanation = generate_deterministic_explanation(analysis_result)
        used_fallback = True
        fallback_reason = "analysis_failed"
    else:
        explanation, used_fallback, fallback_reason = generate_openai_explanation(analysis_result)

    return {
        "success": success,
        "provider": "deterministic" if used_fallback else "openai",
        "model": "deterministic"
        if used_fallback
        else os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "used_fallback": used_fallback,
        "fallback_reason": fallback_reason,
        "explanation": explanation,
        "disclaimer": (analysis_result or {}).get("disclaimer", FALLBACK_DISCLAIMER),
    }


def explain_stock_analysis(user_input: str) -> dict[str, Any]:
    """Run deterministic analysis, then explain it without modifying results."""
    analysis = analyze_stock(user_input)
    llm = generate_llm_explanation(analysis)
    return {
        "success": bool(analysis.get("success", False)),
        "message": analysis.get("message", ""),
        "analysis": analysis,
        "llm": llm,
        "explanation": llm["explanation"],
    }


def _get_max_output_tokens() -> int:
    """Return a positive output-token cap, defaulting safely to 700."""
    try:
        value = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_OUTPUT_TOKENS
    return value if value > 0 else DEFAULT_MAX_OUTPUT_TOKENS


def _get_env_bool(name: str, default: bool = False) -> bool:
    """Read common truthy env values while keeping defaults explicit."""
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_float_format(value: Any, decimals: int = 6) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{int(numeric)}" if decimals == 0 else f"{numeric:.{decimals}f}"


def _format_percent(value: Any) -> str:
    formatted = _safe_float_format(value, 2)
    return "N/A" if formatted == "N/A" else f"{formatted}%"


def _format_metrics_for_prompt(metrics: dict[str, Any]) -> str:
    formatted = _format_metrics_for_display(metrics)
    return (
        f"Directional Accuracy {formatted['directional_accuracy']}, "
        f"Hit Rate {formatted['hit_rate']}, "
        f"Total Active Signals {formatted['total_active_signals']}, "
        f"Correct Signals {formatted['correct_signals']}"
    )


def _format_comparison_for_prompt(comparison: list[dict[str, Any]]) -> list[str]:
    return [
        (
            f"{item.get('indicator', 'Indikator')}: "
            f"Directional Accuracy {_format_percent(item.get('directional_accuracy'))}, "
            f"Hit Rate {_format_percent(item.get('hit_rate'))}, "
            f"Total Active Signals {_safe_float_format(item.get('total_active_signals'), 0)}, "
            f"Correct Signals {_safe_float_format(item.get('correct_signals'), 0)}"
        )
        for item in comparison
    ]


def _format_wfa_config_for_prompt(config: dict[str, Any]) -> str:
    return (
        f"WFA {config.get('in_sample_months', 6)},{config.get('out_sample_months', 3)},"
        f"{config.get('shift_months', 3)} dengan horizon evaluasi "
        f"{config.get('evaluation_horizon_periods', 3)} trading days"
    )


def _format_data_period_for_prompt(analysis_result: dict[str, Any]) -> str:
    period = analysis_result.get("data_period") or {}
    return (
        f"{period.get('start_date', 'N/A')} sampai "
        f"{analysis_result.get('latest_date') or period.get('end_date', 'N/A')}"
    )


def _format_metrics_for_display(metrics: dict[str, Any]) -> dict[str, str]:
    """Format immutable system metrics for concise user-facing display."""
    return {
        "directional_accuracy": _format_percent(metrics.get("directional_accuracy")),
        "hit_rate": _format_percent(metrics.get("hit_rate")),
        "total_active_signals": _safe_float_format(metrics.get("total_active_signals"), 0),
        "correct_signals": _safe_float_format(metrics.get("correct_signals"), 0),
    }


def _format_indicator_comparison(comparison: list[dict[str, Any]]) -> str:
    """Create the deterministic fallback's compact comparison sentence."""
    if not comparison:
        return "Data perbandingan indikator belum tersedia."

    parts = []
    for item in comparison:
        parts.append(
            f"{item.get('indicator', 'Indikator')}: "
            f"Directional Accuracy {_format_percent(item.get('directional_accuracy'))}, "
            f"Hit Rate {_format_percent(item.get('hit_rate'))}, "
            f"Total Active Signals {_safe_float_format(item.get('total_active_signals'), 0)}"
        )
    return "; ".join(parts) + "."


def _contains_internal_field_terms(text: str) -> bool:
    """Return True when provider output leaks implementation field names."""
    normalized = str(text).casefold()
    return any(term in normalized for term in INTERNAL_FIELD_TERMS)


def _contains_forbidden_recommendation_terms(text: str) -> bool:
    """Detect explicit recommendation language while allowing negated disclaimers."""
    normalized = str(text).casefold()
    non_disclaimer_text = normalized
    for phrase in SAFE_DISCLAIMER_PHRASES:
        non_disclaimer_text = non_disclaimer_text.replace(phrase, "")
    return any(term in non_disclaimer_text for term in FORBIDDEN_RECOMMENDATION_TERMS)


def _json_safe(value: Any) -> Any:
    """Round-trip through JSON so prompts never receive pandas/numpy objects."""
    return json.loads(json.dumps(value, default=str, allow_nan=False))
