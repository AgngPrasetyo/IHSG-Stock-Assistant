# scripts/validate_all_latest_signals.py

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[1]

for path in (SCRIPT_DIR, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from services.analysis_service import (  # noqa: E402
    get_sector_best_indicator,
    prepare_latest_analysis_dataframe,
)
from services.mapping_service import load_mapping  # noqa: E402
from services.signal_service import (  # noqa: E402
    MA_CROSSOVER_SIGNAL_COLUMN,
    MACD_TRADE_SIGNAL_COLUMN,
    RSI_SIGNAL_COLUMN,
)
from validate_latest_signals import validate_by_indicator  # noqa: E402


def load_samples() -> pd.DataFrame:
    mapping = load_mapping()
    sample = mapping[
        mapping["is_sample"].astype(str).str.strip().str.casefold().eq("ya")
        & mapping["status_data"].astype(str).str.strip().str.casefold().eq("lengkap")
    ][["sektor", "ticker", "ticker_yfinance"]].copy()

    return sample.sort_values(["sektor", "ticker"]).reset_index(drop=True)


def main() -> None:
    sample = load_samples()
    rows: list[dict[str, object]] = []

    for _, stock in sample.iterrows():
        ticker = str(stock["ticker"])
        ticker_yfinance = str(stock["ticker_yfinance"])
        sector = str(stock["sektor"])

        try:
            best = get_sector_best_indicator(sector)
            if not best:
                rows.append(
                    {
                        "ticker": ticker,
                        "ticker_yfinance": ticker_yfinance,
                        "sector": sector,
                        "best_indicator": None,
                        "latest_date": None,
                        "latest_signal": None,
                        "expected_signal": None,
                        "validation_status": "ERROR_BEST_INDICATOR_TIDAK_TERSEDIA",
                    }
                )
                continue

            best_indicator = str(best["indicator"])
            df = prepare_latest_analysis_dataframe(ticker_yfinance)

            latest = df.iloc[-1]
            prev = df.iloc[-2]
            validation = validate_by_indicator(df, best_indicator)

            rows.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "best_indicator": best_indicator,
                    "rows": len(df),
                    "start_date": df.index.min().strftime("%Y-%m-%d"),
                    "prev_date": df.index[-2].strftime("%Y-%m-%d"),
                    "latest_date": df.index[-1].strftime("%Y-%m-%d"),
                    "prev_close": prev.get("Close"),
                    "latest_close": latest.get("Close"),
                    "latest_signal": validation.get("actual_signal"),
                    "expected_signal": validation.get("expected_signal"),
                    "ma_signal": latest.get(MA_CROSSOVER_SIGNAL_COLUMN),
                    "macd_signal": latest.get(MACD_TRADE_SIGNAL_COLUMN),
                    "rsi_signal": latest.get(RSI_SIGNAL_COLUMN),
                    "sma10_prev": prev.get("SMA10"),
                    "sma50_prev": prev.get("SMA50"),
                    "sma10_latest": latest.get("SMA10"),
                    "sma50_latest": latest.get("SMA50"),
                    "macd_prev": prev.get("MACD"),
                    "macd_signal_prev": prev.get("MACD_Signal"),
                    "macd_latest": latest.get("MACD"),
                    "macd_signal_latest": latest.get("MACD_Signal"),
                    "rsi_prev": prev.get("RSI"),
                    "rsi_latest": latest.get("RSI"),
                    "condition": validation.get("condition"),
                    "validation_status": validation.get("validation_status"),
                }
            )

        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "ticker_yfinance": ticker_yfinance,
                    "sector": sector,
                    "best_indicator": None,
                    "latest_date": None,
                    "latest_signal": None,
                    "expected_signal": None,
                    "validation_status": f"ERROR:{type(exc).__name__}:{exc}",
                }
            )

    result = pd.DataFrame(rows)

    output_path = PROJECT_ROOT / "data" / "validate_all_latest_signals.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    print("=" * 100)
    print("VALIDASI SEMUA SINYAL TERBARU BERDASARKAN ATURAN SISTEM SAAT INI")
    print("=" * 100)
    print()

    display_columns = [
        "ticker",
        "sector",
        "best_indicator",
        "latest_date",
        "latest_signal",
        "expected_signal",
        "validation_status",
        "condition",
    ]

    print(result[display_columns].to_string(index=False))
    print()

    print("=" * 100)
    print("RINGKASAN STATUS VALIDASI")
    print("=" * 100)
    print(result["validation_status"].value_counts().to_string())
    print()

    print("=" * 100)
    print("DATA ERROR / PERLU CEK")
    print("=" * 100)

    need_check = result[
        result["validation_status"].astype(str).str.contains("ERROR|PERLU_CEK", case=False, na=False)
    ]

    if need_check.empty:
        print("Tidak ada data ERROR atau PERLU_CEK.")
    else:
        print(need_check[display_columns].to_string(index=False))

    print()
    print(f"File hasil validasi disimpan ke: {output_path}")


if __name__ == "__main__":
    main()
