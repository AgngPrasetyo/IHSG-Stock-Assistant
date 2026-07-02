from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from services.analysis_service import analyze_stock
from services.mapping_service import load_mapping


OUTPUT_PATH = PROJECT_ROOT / "data" / "audit_post_signal_validation.csv"
CSV_COLUMNS = [
    "ticker",
    "sector",
    "best_indicator",
    "latest_date",
    "latest_signal",
    "horizon",
    "signal_date",
    "target_date",
    "signal",
    "close_t",
    "close_future",
    "actual_direction",
    "return_pct",
    "status",
    "message",
]


def main() -> None:
    mapping = load_mapping()
    sample = mapping[
        (mapping["is_sample"].astype(str).str.strip().str.casefold() == "ya")
        & (mapping["status_data"].astype(str).str.strip().str.casefold() == "lengkap")
    ].copy()

    rows: list[dict[str, object]] = []

    for _, stock in sample.iterrows():
        ticker = stock["ticker"]
        sector = stock["sektor"]

        try:
            result = analyze_stock(str(ticker))
            if not result.get("success"):
                rows.append(
                    {
                        "ticker": ticker,
                        "sector": sector,
                        "best_indicator": None,
                        "latest_date": None,
                        "latest_signal": None,
                        "horizon": None,
                        "status": "ERROR_ANALYZE_STOCK",
                        "message": result.get("message"),
                    }
                )
                continue

            for item in result.get("post_signal_validation", []):
                rows.append(
                    {
                        "ticker": result.get("ticker", ticker),
                        "sector": result.get("sector", sector),
                        "best_indicator": result.get("best_indicator"),
                        "latest_date": result.get("latest_date"),
                        "latest_signal": result.get("latest_signal"),
                        **item,
                    }
                )

        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "sector": sector,
                    "best_indicator": None,
                    "latest_date": None,
                    "latest_signal": None,
                    "horizon": None,
                    "status": f"ERROR:{type(exc).__name__}",
                    "message": str(exc),
                }
            )

    result = pd.DataFrame(rows, columns=CSV_COLUMNS)
    result.to_csv(OUTPUT_PATH, index=False)

    print("=" * 100)
    print("AUDIT VALIDASI LANJUTAN SINYAL TERBARU")
    print("=" * 100)
    print(result["status"].value_counts(dropna=False).to_string())
    print()
    print(f"File hasil audit disimpan ke: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()