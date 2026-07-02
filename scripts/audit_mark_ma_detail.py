from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd
from services.analysis_service import prepare_latest_analysis_dataframe
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

def main() -> None:
    df = prepare_latest_analysis_dataframe("MARK.JK")

    audit = df.loc[
        "2026-06-01":"2026-06-30",
        [
            "Close",
            "SMA20",
            "SMA50",
            "MA_Crossover_Signal",
        ],
    ].copy()

    audit["SMA20_minus_SMA50"] = audit["SMA20"] - audit["SMA50"]

    audit["Posisi_MA"] = "SMA20 = SMA50"
    audit.loc[audit["SMA20_minus_SMA50"] > 0, "Posisi_MA"] = "SMA20 di atas SMA50"
    audit.loc[audit["SMA20_minus_SMA50"] < 0, "Posisi_MA"] = "SMA20 di bawah SMA50"

    print("=" * 100)
    print("AUDIT DETAIL MA CROSSOVER MARK")
    print("=" * 100)
    print()
    print(audit.to_string())
    print()

    print("=" * 100)
    print("VALIDASI PERUBAHAN POSISI MA")
    print("=" * 100)

    previous_position = None

    for date, row in audit.iterrows():
        current_position = row["Posisi_MA"]
        signal = row["MA_Crossover_Signal"]

        if previous_position is not None and current_position != previous_position:
            print(
                f"{date.strftime('%Y-%m-%d')} | "
                f"Perubahan posisi: {previous_position} -> {current_position} | "
                f"Sinyal: {signal}"
            )

        previous_position = current_position

    print()
    print("=" * 100)
    print("KESIMPULAN KHUSUS 2026-06-22")
    print("=" * 100)

    prev_date = pd.Timestamp("2026-06-19")
    latest_date = pd.Timestamp("2026-06-22")

    prev = df.loc[prev_date]
    latest = df.loc[latest_date]

    print(f"Tanggal sebelumnya : {prev_date.strftime('%Y-%m-%d')}")
    print(f"SMA20 sebelumnya   : {prev['SMA20']:.4f}")
    print(f"SMA50 sebelumnya   : {prev['SMA50']:.4f}")
    print(f"Selisih sebelumnya : {prev['SMA20'] - prev['SMA50']:.4f}")
    print()
    print(f"Tanggal terbaru    : {latest_date.strftime('%Y-%m-%d')}")
    print(f"SMA20 terbaru      : {latest['SMA20']:.4f}")
    print(f"SMA50 terbaru      : {latest['SMA50']:.4f}")
    print(f"Selisih terbaru    : {latest['SMA20'] - latest['SMA50']:.4f}")
    print(f"Sinyal terbaru     : {latest['MA_Crossover_Signal']}")

    buy_valid = (
        prev["SMA20"] <= prev["SMA50"]
        and latest["SMA20"] > latest["SMA50"]
        and latest["MA_Crossover_Signal"] == "BUY"
    )

    if buy_valid:
        print()
        print("Kesimpulan: BUY pada 2026-06-22 VALID sebagai crossover baru.")
    else:
        print()
        print("Kesimpulan: BUY pada 2026-06-22 PERLU DICEK kembali.")


if __name__ == "__main__":
    main()