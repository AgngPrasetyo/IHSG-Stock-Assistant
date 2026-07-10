from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.analysis_service import analyze_stock  # noqa: E402
from services.llm_service import build_llm_context  # noqa: E402


def export_llm_payload(query: str = "Analisis saham BBCA") -> Path:
    """Export deterministic analysis and LLM context for inspection."""
    output_dir = PROJECT_ROOT / "data" / "llm_payload_examples"
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis = analyze_stock(query)
    context = build_llm_context(analysis)

    ticker = analysis.get("ticker", "UNKNOWN")
    latest_date = analysis.get("latest_date", "unknown")
    output_path = output_dir / f"llm_payload_{ticker}_{latest_date}.json"

    payload = {
    "user_query": query,
    "analysis": analysis,
    "llm_context": context,
    "llm_policy": {
        "role": "Menjelaskan hasil analisis teknikal deterministik sebagai asisten pendukung keputusan.",
        "can_change_signal": False,
        "can_change_metrics": False,
        "can_change_best_indicator": False,
        "can_calculate_wfa": False,
        "can_give_final_investment_recommendation": False,
    },
    "note": (
        "analysis berisi hasil deterministik dari sistem. "
        "llm_context adalah ringkasan yang digunakan untuk membuat penjelasan bahasa alami. "
        "LLM tidak mengubah sinyal, indikator, atau metrik."
    ),
}

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "Analisis saham BBCA"
    output_path = export_llm_payload(query)
    print(f"LLM payload exported to: {output_path}")


if __name__ == "__main__":
    main()