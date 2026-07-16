from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.data_service import WARMUP_START_DATE, LATEST_DATA_END_DATE, load_or_fetch_price_data


def check_latest_ma_condition(ticker_yfinance: str, refresh: bool = False) -> None:
    df = load_or_fetch_price_data(
        ticker_yfinance,
        start_date=WARMUP_START_DATE,
        end_date=LATEST_DATA_END_DATE,
        use_cache=not refresh,
    )

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

    print("Jumlah baris data:", len(df))
    print("Tanggal awal:", df.index.min())
    print("Tanggal akhir:", df.index.max())

    if len(df) < 50:
        print("\nData kurang dari 50 baris. SMA50 belum bisa dihitung.")
        print(df.tail(10)[["Close"]])
        return

    df["SMA10"] = df["Close"].rolling(window=10, min_periods=10).mean()
    df["SMA50"] = df["Close"].rolling(window=50, min_periods=50).mean()

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    sma10_now = latest["SMA10"]
    sma50_now = latest["SMA50"]
    sma10_prev = previous["SMA10"]
    sma50_prev = previous["SMA50"]

    if pd.isna(sma10_now) or pd.isna(sma50_now) or pd.isna(sma10_prev) or pd.isna(sma50_prev):
        print("\nSMA masih NaN. Cek data Close terakhir:")
        print(df.tail(60)[["Close", "SMA10", "SMA50"]])
        return

    if sma10_prev <= sma50_prev and sma10_now > sma50_now:
        kondisi = "SMA10 memotong ke atas SMA50 pada data terakhir."
        sinyal = "BUY"
    elif sma10_prev >= sma50_prev and sma10_now < sma50_now:
        kondisi = "SMA10 memotong ke bawah SMA50 pada data terakhir."
        sinyal = "SELL"
    elif sma10_now > sma50_now:
        kondisi = "SMA10 > SMA50, tetapi tidak terjadi crossover baru pada data terakhir."
        sinyal = "HOLD"
    elif sma10_now < sma50_now:
        kondisi = "SMA10 < SMA50, tetapi tidak terjadi crossover baru pada data terakhir."
        sinyal = "HOLD"
    else:
        kondisi = "SMA10 sama dengan SMA50 pada data terakhir."
        sinyal = "HOLD"

    result = pd.DataFrame(
        [
            {
                "Tanggal": pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d"),
                "Close": latest["Close"],
                "SMA10": round(sma10_now, 2),
                "SMA50": round(sma50_now, 2),
                "SMA10 Hari Sebelumnya": round(sma10_prev, 2),
                "SMA50 Hari Sebelumnya": round(sma50_prev, 2),
                "Tanggal Sebelumnya": pd.Timestamp(df.index[-2]).strftime("%Y-%m-%d"),
                "Kondisi": kondisi,
                "Sinyal": sinyal,
            }
        ]
    )

    print("\nHasil pengecekan MA Crossover:")
    print(result.to_string(index=False))


if __name__ == "__main__":
    check_latest_ma_condition("BBRI.JK", refresh=True)