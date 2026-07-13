"""Safe natural-language explanations for deterministic stock analysis results."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from services.analysis_service import analyze_stock 

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")



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
    "volume_ma20",
)


def _contains_disallowed_script(text: str) -> bool:
    """Detect unexpected non-Indonesian scripts in the explanation output."""
    return re.search(r"[\u0600-\u06FF]", str(text)) is not None


def _format_last_active_signal_for_prompt(value: Any) -> str:
    if not isinstance(value, dict):
        return "Belum ada sinyal aktif BUY/SELL pada periode data yang tersedia."

    signal = str(value.get("signal") or "").strip().upper()
    signal_date = value.get("date")

    if signal not in {"BUY", "SELL"} or not signal_date:
        return "Belum ada sinyal aktif BUY/SELL pada periode data yang tersedia."

    return f"{signal} pada {signal_date}"


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
        "sektor": analysis_result.get("sector"),
        "periode_data": _format_data_period_for_prompt(analysis_result),
        "konfigurasi_evaluasi": _format_wfa_config_for_prompt(
            analysis_result.get("wfa_config") or {}
        ),
        "indikator_terbaik": analysis_result.get("best_indicator"),
        "sinyal_teknikal_saat_ini": analysis_result.get("latest_signal"),
        "konteks_sinyal": _format_signal_context_for_prompt(analysis_result),
        "tanggal_terbaru": analysis_result.get("latest_date"),
        "harga_penutupan_terakhir": analysis_result.get("latest_close"),
        "metrik_evaluasi": _format_metrics_for_prompt(analysis_result.get("metrics") or {}),
        "perbandingan_indikator": _format_comparison_for_prompt(
            analysis_result.get("indicator_comparison") or []
        ),
        "dasar_pemilihan_indikator": analysis_result.get("best_indicator_basis"),
        "catatan_kualitas_metrik": (analysis_result.get("metric_quality_note") or {}).get("message"),
        "catatan_pendukung_keputusan": analysis_result.get("decision_support_note"),
        "sinyal_aktif_terakhir": _format_last_active_signal_for_prompt(
            analysis_result.get("last_active_signal")
        ),
        "disclaimer": analysis_result.get("disclaimer", FALLBACK_DISCLAIMER),
    }
    if analysis_result.get("stock_name") is not None:
        context["nama_saham"] = analysis_result["stock_name"]
    return _json_safe({key: value for key, value in context.items() if value is not None})


def _format_signal_context_for_prompt(analysis_result: dict[str, Any]) -> str:
    indicator = str(analysis_result.get("best_indicator") or "indikator terbaik")
    signal = str(analysis_result.get("latest_signal") or "HOLD").upper()
    last_active = _format_last_active_signal_for_prompt(
        analysis_result.get("last_active_signal")
    )

    if signal == "HOLD":
        return (
            f"Sinyal teknikal saat ini adalah HOLD. "
            f"Belum ada sinyal BUY atau SELL aktif pada tanggal terakhir berdasarkan {indicator}. "
            f"Sinyal aktif terakhir adalah {last_active}."
        )

    return (
        f"Sinyal teknikal saat ini adalah {signal} berdasarkan {indicator}. "
        f"Sinyal ini berasal dari aturan indikator terbaik sektor."
    )


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
    - Directional Accuracy adalah persentase kecocokan seluruh sinyal aktif BUY/SELL terhadap arah harga berdasarkan Average Forward Return pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham.
    - Average Forward Return adalah rata-rata return harga setelah sinyal pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham.
    - Correct Signals adalah jumlah sinyal BUY/SELL yang sesuai berdasarkan Average Forward Return tersebut.
    - Hit Rate adalah rata-rata keberhasilan sinyal aktif setiap periode evaluasi, bukan selalu sama dengan Directional Accuracy.
    - Jika sinyal teknikal saat ini adalah HOLD, jelaskan bahwa belum ada sinyal BUY atau SELL aktif pada tanggal terakhir berdasarkan indikator terbaik.
    - Jangan menyimpulkan HOLD hanya dari posisi harga terhadap SMA.
    - Untuk MA Crossover, BUY atau SELL hanya muncul saat terjadi crossover SMA10 dan SMA50 pada data terbaru; posisi SMA10 di atas/bawah SMA50 saja bukan sinyal baru.
    - Untuk MACD, BUY atau SELL hanya muncul saat terjadi crossover baru antara MACD Line dan Signal Line; posisi garis saja bukan sinyal baru.
    - Untuk RSI, oversold tidak otomatis BUY dan overbought tidak otomatis SELL; sistem menunggu RSI keluar dari area oversold atau overbought.
    - Gunakan istilah “evaluasi Average Forward Return pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham”.
    - Jika tersedia sinyal aktif terakhir, jelaskan secara singkat setelah sinyal teknikal saat ini. Contoh: “Sinyal aktif terakhir adalah BUY pada 2026-06-18.”
    - Untuk penjelasan utama kepada pengguna, jelaskan aturan dasar indikator: crossover SMA10/SMA50, crossover MACD Line dan Signal Line, atau RSI keluar dari area oversold/overbought.
    - Jangan menyebut VolMA20, Volume_MA20, threshold histogram, filter volume, filter tren, atau detail filter teknis internal karena metode final tidak menggunakan filter tambahan.
    - Tuliskan “MA Crossover” dengan spasi. Jangan menulis “MACrossover”.
    - Pastikan selalu ada spasi setelah tanda baca seperti titik, koma, dan persen.
    - Gunakan bahasa Indonesia sepenuhnya. Jangan menyisipkan bahasa asing atau karakter non-Latin di luar istilah teknikal umum seperti BUY, SELL, HOLD, MACD, RSI, SMA, dan WFA.
    - Gunakan konteks_sinyal sebagai sumber utama untuk menjelaskan sinyal saat ini dan sinyal aktif terakhir.
    - Jangan menyalin angka Volume, VolMA20, atau nilai filter teknis internal ke dalam penjelasan utama.
    - Jangan menambahkan spasi di dalam angka desimal. Tulis 48.15%, bukan 48. 15%.
    - Pastikan ada spasi setelah koma dan sebelum kata berikutnya.
    - Gunakan ticker utama tanpa suffix bursa, misalnya MARK, BBCA, atau ADRO. Jangan menulis MARK.JK atau MARK. JK pada penjelasan utama.
    - Gunakan istilah “terbaik berdasarkan metrik evaluasi”, bukan “paling kuat”, agar tidak terkesan sebagai rekomendasi investasi.
    - Gunakan istilah “indikator terbaik berdasarkan metrik evaluasi”, bukan “unggul”, “paling kuat”, atau “lebih baik” agar penjelasan tetap netral.
    - Indikator terbaik dipilih berdasarkan Directional Accuracy tertinggi, bukan berdasarkan Hit Rate atau Correct Signals.
    - Jika Hit Rate atau Correct Signals indikator lain lebih tinggi, jelaskan bahwa keduanya adalah metrik pendukung, sedangkan pemilihan indikator terbaik tetap mengikuti Directional Accuracy.
    - Gunakan istilah “indikator terbaik berdasarkan Directional Accuracy”, bukan “indikator paling kuat”, “unggul”, atau “lebih baik”.
    - Jelaskan bahwa indikator terbaik dipilih berdasarkan hasil evaluasi historis WFA pada sektor saham terkait.
    - Jika Directional Accuracy berada di rentang 50% sampai 60%, jelaskan bahwa performa hanya sedikit di atas ambang 50% dan perlu konfirmasi tambahan.
    - Jika ada indikator pembanding dengan Total Active Signals 0, jelaskan bahwa indikator tersebut tidak memiliki nilai evaluasi final pada rangkuman sektor ini.
    - Berikan catatan pendukung keputusan yang netral: pertimbangkan indikator pembanding, tren harga, likuiditas, kondisi sektor, sentimen pasar, dan faktor fundamental emiten.
    - Saat membandingkan indikator, gunakan frasa “mencatat Directional Accuracy tertinggi dibanding indikator lain dalam data ini”, bukan “menunjukkan kecocokan sinyal aktif yang lebih tinggi”, “lebih unggul”, atau “lebih kuat”.
    - Gunakan istilah periode data saham untuk data terbaru aplikasi dan periode evaluasi WFA utama untuk metrik evaluasi indikator.
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
    signal = str(analysis_result.get("latest_signal", "HOLD")).upper()

    metrics = analysis_result.get("metrics") or {}
    accuracy = _format_percent(metrics.get("directional_accuracy"))
    hit_rate = _format_percent(metrics.get("hit_rate"))
    active = _safe_float_format(metrics.get("total_active_signals"), 0)
    correct = _safe_float_format(metrics.get("correct_signals"), 0)

    last_active_signal = _format_last_active_signal_for_prompt(
        analysis_result.get("last_active_signal")
    )

    if signal == "HOLD":
        signal_sentence = (
            "Sinyal sistem saat ini adalah HOLD. "
            "Belum ada sinyal BUY/SELL aktif pada tanggal terakhir. "
            f"Sinyal aktif terakhir adalah {last_active_signal}."
        )
    else:
        signal_sentence = f"Sinyal sistem saat ini adalah {signal}."

    comparison = _format_indicator_comparison(
        analysis_result.get("indicator_comparison") or []
    )

    metric_quality_note = (
        analysis_result.get("metric_quality_note") or {}
    ).get("message", "")

    decision_support_note = analysis_result.get("decision_support_note", "")
    basis = analysis_result.get(
        "best_indicator_basis",
        "Indikator terbaik dipilih berdasarkan hasil evaluasi WFA.",
    )

    return (
        f"Ringkasan saham: {ticker} berada pada sektor {sector}. "
        f"Indikator terbaik sektor menurut WFA adalah {indicator}.\n\n"

        f"Sinyal teknikal saat ini: {signal_sentence} "
        f"Penjelasan teknikal disusun berdasarkan aturan indikator terbaik sektor, "
        f"tanpa mengubah hasil perhitungan sistem.\n\n"

        f"Evaluasi indikator terbaik: {basis} "
        f"Directional Accuracy {accuracy} menjadi dasar pemilihan indikator terbaik "
        f"karena mengukur kecocokan sinyal BUY/SELL terhadap arah harga berdasarkan "
        f"Average Forward Return pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham. "
        f"{metric_quality_note} "
        f"Hit Rate {hit_rate}, Total Active Signals {active}, dan Correct Signals {correct} "
        f"digunakan sebagai metrik pendukung.\n\n"

        f"Perbandingan indikator lain: {comparison}\n\n"

        f"Catatan pendukung keputusan: {decision_support_note} "
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
        explanation = _normalize_explanation_text(explanation)
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

    if _contains_disallowed_script(explanation):
        return generate_deterministic_explanation(analysis_result), True, "unexpected_script_in_output"

    if not explanation or _contains_forbidden_recommendation_terms(explanation):
        return generate_deterministic_explanation(analysis_result), True, "unsafe_output"

    if "bantuan analisis teknikal" not in explanation.casefold():
        explanation = f"{explanation}\n\n{FALLBACK_DISCLAIMER}"

    explanation = _normalize_explanation_text(explanation)
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


def _normalize_explanation_text(text: str) -> str:
    """Clean small spacing and typography issues in LLM output without breaking decimals or tickers."""
    normalized = str(text or "").strip()
    normalized = re.sub(r"\b([A-Z0-9]{2,6})\s*\.\s*JK\b", r"\1", normalized)
    replacements = {
        "MACrossover": "MA Crossover",
        "MA crossover": "MA Crossover",
        "tanggalterakhir": "tanggal terakhir",
        "terbarujuga": "terbaru juga",
        "aturanindikator": "aturan indikator",
        "DirectionalAccuracy": "Directional Accuracy",
        "indikatorterbaik": "indikator terbaik",
        "investasifinal": "investasi final",
        "metrikevaluasi": "metrik evaluasi",
        "tanpamengubah": "tanpa mengubah",
        "merupakanbantuan": "merupakan bantuan",
        "sertaRSI": "serta RSI",
        "Hit Rate": "Hit Rate",
        "MARK. JK": "MARK.JK",
        "WFA 6, 3, 3": "WFA 6,3,3",
        "horizon evaluasi 3 trading days": "evaluasi Average Forward Return pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham",
        "3 trading days": "T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham",
        "setelah 3 hari perdagangan": "berdasarkan Average Forward Return pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham",
        "filter tren SMA50": "aturan indikator",
        "menunjukkan kecocokan sinyal aktif yang lebih tinggi dibanding indikator lain dalam data ini": "mencatat Directional Accuracy tertinggi dibanding indikator lain dalam data ini",
    }

    replacements.update({
        "%,Hit": "%, Hit",
        "crossoveryang": "crossover yang",
        "terkonfirmasioleh": "terkonfirmasi oleh",
        "dengankonfirmasi": "dengan konfirmasi",
        "hasilsistem": "hasil sistem",
        "secarakeseluruhan": "secara keseluruhan",
        "evaluasi3": "evaluasi 3",
        "baruyang": "baru yang",
        "teknikalterbaru": "teknikal terbaru",
        "sampai 2026-06-26dianalisis": "sampai 2026-06-26 dianalisis",
        "SELLhanya": "SELL hanya",
        "BUYatau": "BUY atau",
        "27total": "27 total",
        "terbaruseperti": "terbaru seperti",
    })
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    # Jangan pecah angka desimal seperti 48.15 atau ticker seperti MARK.JK.
    normalized = re.sub(r"(?<!\d)([.!?])(?=\S)", r"\1 ", normalized)

    # Tambahkan spasi setelah koma hanya jika bukan pola angka/konfigurasi seperti 6,3,3.
    normalized = re.sub(r"(?<!\d),(?=\S)", ", ", normalized)

    # Tambahkan spasi setelah persen jika langsung diikuti huruf.
    normalized = re.sub(r"(?<=%)(?=[A-Za-zÀ-ÿ])", " ", normalized)

    # Perbaiki kata yang sering menempel.
    normalized = re.sub(r"\bHit Rate(?=\d)", "Hit Rate ", normalized)
    normalized = re.sub(r"\bDirectional Accuracy(?=\d)", "Directional Accuracy ", normalized)
    normalized = re.sub(r"\bserta(?=RSI\b)", "serta ", normalized)

    # Sederhanakan detail teknis internal untuk tampilan utama.
    normalized = re.sub(
        r",?\s*dan Volume [\d.]+ yang berada di bawah VolMA20 [\d.]+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\bVolMA20\b", "konfirmasi sistem", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bVolume_MA20\b", "konfirmasi sistem", normalized, flags=re.IGNORECASE)

    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"(?<=[a-zA-Z])(?=dianalisis\b)", " ", normalized)
    normalized = re.sub(r"(?<=[a-zA-Z])(?=terkonfirmasi\b)", " ", normalized)
    normalized = re.sub(r"(?<=[a-zA-Z])(?=yang\b)", " ", normalized)
    normalized = re.sub(r"\b([A-Z]{4})\. JK\b", r"\1.JK", normalized)
    normalized = re.sub(r"(?<=evaluasi)(?=\d)", " ", normalized)
    normalized = re.sub(r"(?<=baru)(?=yang\b)", " ", normalized)
    normalized = re.sub(r"(?<=teknikal)(?=terbaru\b)", " ", normalized)
    normalized = re.sub(r"(?<=\d)(?=total\b)", " ", normalized)
    normalized = re.sub(r"(?<=SELL)(?=hanya\b)", " ", normalized)
    normalized = re.sub(r"(?<=BUY)(?=atau\b)", " ", normalized)
    return normalized.strip()


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
    label = config.get(
        "evaluation_horizon_label",
        "T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham",
    )
    method = config.get("evaluation_method", "Average Forward Return")

    return (
        f"WFA {config.get('in_sample_months', 6)},"
        f"{config.get('out_sample_months', 3)},"
        f"{config.get('shift_months', 3)} dengan evaluasi {method} pada {label}"
    )


def _format_data_period_for_prompt(analysis_result: dict[str, Any]) -> str:
    period = analysis_result.get("data_period") or {}

    start_date = period.get("start_date", "N/A")
    latest_date = (
        analysis_result.get("latest_date")
        or period.get("latest_data_date")
        or "N/A"
    )
    wfa_start = period.get("wfa_evaluation_start_date", start_date)
    wfa_end = period.get("wfa_evaluation_end_date", "N/A")

    return (
        f"Data saham tersedia dari {start_date} sampai {latest_date}. "
        f"Evaluasi WFA utama digunakan untuk menentukan indikator terbaik "
        f"pada periode {wfa_start} sampai {wfa_end}."
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

