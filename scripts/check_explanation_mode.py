from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.analysis_service import analyze_stock
from services.llm_service import generate_llm_explanation


def main() -> None:
    analysis_result = analyze_stock("BBCA")
    explanation_result = generate_llm_explanation(analysis_result)

    print("Provider       :", explanation_result.get("provider"))
    print("Model          :", explanation_result.get("model"))
    print("Used fallback  :", explanation_result.get("used_fallback"))
    print("Fallback reason:", explanation_result.get("fallback_reason"))
    print()
    print("Penjelasan:")
    print(explanation_result.get("explanation"))


if __name__ == "__main__":
    main()