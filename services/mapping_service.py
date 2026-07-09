"""Utilities for reading and validating stock ticker mapping data."""

from __future__ import annotations

import re
import string
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAPPING_FILE = PROJECT_ROOT / "data" / "mapping_saham_final.xlsx"

REQUIRED_COLUMNS = [
    "ticker",
    "ticker_yfinance",
    "sektor",
    "is_sample",
    "status_data",
    "data_start",
    "data_end",
    "jumlah_data",
    "catatan",
]

UNAVAILABLE_MESSAGE = "Kode saham belum tersedia dalam mapping sistem."
INCOMPLETE_DATA_MESSAGE = "Data saham belum memenuhi kriteria kelengkapan data."
VALID_MESSAGE = "Kode saham valid dan tersedia dalam mapping sistem."

INVALID_INTENT_MESSAGE = (
    "Input belum sesuai dengan konteks analisis teknikal saham. "
    "Silakan masukkan kode saham saja, misalnya BBCA, atau gunakan format seperti analisis saham BBCA."
)

_STOCK_ANALYSIS_INTENT_KEYWORDS = {
    "saham",
    "analisis",
    "analisa",
    "teknikal",
    "sinyal",
    "indikator",
    "harga",
    "tren",
    "trend",
    "buy",
    "sell",
    "hold",
    "crossover",
    "macd",
    "rsi",
    "moving average",
    "ma",
    "wfa",
    "evaluasi",
    "emiten",
    "bursa",
    "ihsg",
    "close",
    "penutupan",
    "cek",
    "check",
    "lihat",
    "periksa",
    "pantau",
}

_NON_STOCK_INTENT_KEYWORDS = {
    "kesehatan",
    "riwayat kesehatan",
    "penyakit",
    "medis",
    "dokter",
    "rumah sakit",
    "obat",
    "diagnosis",
    "diagnosa",
    "pasien",
    "gejala",
    "sakit",
    "makan",
    "makanan",
    "minum",
    "rasa",
    "enak",
    "lezat",
    "sedap",
    "lapar",
    "haus",
    "masak",
    "memasak",
    "resep",
    "alamat",
    "lokasi",
    "rumah",
    "biodata",
    "sejarah",
    "berdiri",
    "pendiri",
}

STOCK_DISPLAY_INFO = {
    "BBCA": {"stock_name": "Bank Central Asia", "aliases": ["bca", "bank bca", "bank central asia"]},
    "BBRI": {"stock_name": "Bank Rakyat Indonesia", "aliases": ["bri", "bank bri", "bank rakyat indonesia"]},
    "BMRI": {"stock_name": "Bank Mandiri", "aliases": ["mandiri", "bank mandiri"]},
    "SMMA": {"stock_name": "Sinar Mas Multiartha", "aliases": ["sinar mas multiartha", "sinarmas multiartha"]},
    "DNET": {"stock_name": "Indoritel Makmur Internasional", "aliases": ["indoritel", "indoritel makmur"]},
    "BBNI": {"stock_name": "Bank Negara Indonesia", "aliases": ["bni", "bank bni", "bank negara indonesia"]},
    "BNLI": {"stock_name": "Bank Permata", "aliases": ["permata", "bank permata"]},
    "CASA": {"stock_name": "Capital Financial Indonesia", "aliases": ["capital financial", "casa"]},
    "BRIS": {"stock_name": "Bank Syariah Indonesia", "aliases": ["bsi", "bank bsi", "bank syariah indonesia"]},
    "MEGA": {"stock_name": "Bank Mega", "aliases": ["mega", "bank mega"]},
    "ASII": {"stock_name": "Astra International", "aliases": ["astra", "astra international"]},
    "IMPC": {"stock_name": "Impack Pratama Industri", "aliases": ["impack", "impack pratama"]},
    "UNTR": {"stock_name": "United Tractors", "aliases": ["united tractors", "untr"]},
    "BNBR": {"stock_name": "Bakrie & Brothers", "aliases": ["bakrie", "bakrie brothers"]},
    "SUNI": {"stock_name": "Sunindo Pratama", "aliases": ["sunindo", "sunindo pratama"]},
    "JTPE": {"stock_name": "Jasuindo Tiga Perkasa", "aliases": ["jasuindo", "jasuindo tiga perkasa"]},
    "HEXA": {"stock_name": "Hexindo Adiperkasa", "aliases": ["hexindo", "hexindo adiperkasa"]},
    "VISI": {"stock_name": "Satu Visi Putra", "aliases": ["satu visi", "satu visi putra"]},
    "MARK": {"stock_name": "Mark Dynamics Indonesia", "aliases": ["mark dynamics", "mark dynamics indonesia"]},
    "ARNA": {"stock_name": "Arwana Citramulia", "aliases": ["arwana", "arwana citramulia"]},
    "DCII": {"stock_name": "DCI Indonesia", "aliases": ["dci", "dci indonesia"]},
    "GOTO": {"stock_name": "GoTo Gojek Tokopedia", "aliases": ["goto", "gojek", "tokopedia", "gojek tokopedia"]},
    "BELI": {"stock_name": "Global Digital Niaga", "aliases": ["blibli", "global digital niaga"]},
    "MLPT": {"stock_name": "Multipolar Technology", "aliases": ["multipolar technology", "multipolar"]},
    "EMTK": {"stock_name": "Elang Mahkota Teknologi", "aliases": ["emtek", "elang mahkota teknologi"]},
    "BUKA": {"stock_name": "Bukalapak", "aliases": ["bukalapak", "buka"]},
    "WIFI": {"stock_name": "Solusi Sinergi Digital", "aliases": ["solusi sinergi digital", "surge", "wifi"]},
    "CYBR": {"stock_name": "ITSEC Asia", "aliases": ["itsec", "itsec asia", "cyber"]},
    "MTDL": {"stock_name": "Metrodata Electronics", "aliases": ["metrodata", "metrodata electronics"]},
    "MSTI": {"stock_name": "Mastersystem Infotama", "aliases": ["mastersystem", "mastersystem infotama"]},
    "BYAN": {"stock_name": "Bayan Resources", "aliases": ["bayan", "bayan resources"]},
    "DSSA": {"stock_name": "Dian Swastatika Sentosa", "aliases": ["dian swastatika", "dian swastatika sentosa"]},
    "CUAN": {"stock_name": "Petrindo Jaya Kreasi", "aliases": ["petrindo", "petrindo jaya kreasi"]},
    "ADRO": {"stock_name": "Alamtri Resources Indonesia", "aliases": ["adaro", "alamtri", "alamtri resources"]},
    "ADMR": {"stock_name": "Adaro Minerals Indonesia", "aliases": ["adaro minerals", "adaro mineral", "adaro minerals indonesia"]},
    "BUMI": {"stock_name": "Bumi Resources", "aliases": ["bumi", "bumi resources"]},
    "TCPI": {"stock_name": "Transcoal Pacific", "aliases": ["transcoal", "transcoal pacific"]},
    "PTRO": {"stock_name": "Petrosea", "aliases": ["petrosea", "ptro"]},
    "GEMS": {"stock_name": "Golden Energy Mines", "aliases": ["golden energy", "golden energy mines"]},
    "PGAS": {"stock_name": "Perusahaan Gas Negara", "aliases": ["pgas", "gas negara", "perusahaan gas negara"]},
}

_TOKEN_STOPWORDS = {
    "ANALISIS",
    "ANALISA",
    "SAHAM",
    "TOLONG",
    "CEK",
    "CHECK",
    "LIHAT",
    "UNTUK",
    "KODE",
    "EMITEN",
    "MENGANALISIS",
    "MENGENAI",
    "APAKAH",
    "ITU",
}

_PUNCTUATION_TRANSLATION = str.maketrans({char: " " for char in string.punctuation})


def load_mapping(mapping_path: str | Path = MAPPING_FILE) -> pd.DataFrame:
    """Read the stock mapping Excel file and validate required columns."""
    path = Path(mapping_path)

    if not path.exists():
        raise FileNotFoundError(f"File mapping saham tidak ditemukan: {path}")

    try:
        mapping_df = pd.read_excel(path)
    except Exception as exc:
        raise ValueError(f"Gagal membaca file mapping saham: {path}") from exc

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in mapping_df.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Kolom wajib mapping saham tidak lengkap: {missing}")

    mapping_df = mapping_df.copy()
    mapping_df["ticker"] = mapping_df["ticker"].astype(str).map(normalize_ticker)
    mapping_df["status_data"] = mapping_df["status_data"].astype(str).str.strip()
    mapping_df["stock_name"] = mapping_df["ticker"].map(
        lambda ticker: STOCK_DISPLAY_INFO.get(ticker, {}).get("stock_name", "")
    )
    mapping_df["aliases"] = mapping_df["ticker"].map(
        lambda ticker: STOCK_DISPLAY_INFO.get(ticker, {}).get("aliases", [])
    )
    return mapping_df


def normalize_search_text(input_text: str | None) -> str:
    """Normalize stock names and aliases for deterministic matching."""
    if input_text is None:
        return ""

    text = str(input_text).casefold().replace("&", " ")
    text = text.translate(_PUNCTUATION_TRANSLATION)
    return re.sub(r"\s+", " ", text).strip()


def normalize_ticker(input_text: str | None) -> str:
    """Normalize ticker input or extract the most likely ticker from a sentence."""
    if input_text is None:
        return ""

    text = str(input_text).strip().upper()
    if not text:
        return ""

    candidates = re.findall(r"\b[A-Z0-9]{2,6}(?:\.JK)?\b", text)
    cleaned_candidates = []

    for candidate in candidates:
        cleaned = candidate.removesuffix(".JK")
        if cleaned not in _TOKEN_STOPWORDS:
            cleaned_candidates.append(cleaned)

    if cleaned_candidates:
        return cleaned_candidates[-1]

    return text.removesuffix(".JK")


def resolve_ticker(input_text: str | None) -> str | None:

    """
    Mencari ticker IDX yang tersedia dari input pengguna.

    Fungsi ini mendukung input berupa kode ticker, ticker dengan suffix .JK,
    nama emiten, atau alias resmi yang ditentukan di STOCK_DISPLAY_INFO.
    Jika terdapat beberapa token pada kalimat, fungsi memilih token yang
    benar-benar tersedia di mapping saham.
    """

    mapping_df = load_mapping()
    normalized_ticker = normalize_ticker(input_text)
    available_tickers = set(mapping_df["ticker"].dropna().astype(str))

    if normalized_ticker in available_tickers:
        return normalized_ticker

    raw_text = str(input_text or "").upper()
    token_candidates = re.findall(r"\b[A-Z0-9]{2,6}(?:\.JK)?\b", raw_text)

    valid_token_candidates = [
        candidate.removesuffix(".JK")
        for candidate in token_candidates
        if candidate.removesuffix(".JK") in available_tickers
    ]

    if valid_token_candidates:
        return valid_token_candidates[-1]

    normalized_input = normalize_search_text(input_text)
    if not normalized_input:
        return None

    alias_matches = []
    for _, row in mapping_df.iterrows():
        ticker = str(row["ticker"])
        search_terms = [row.get("stock_name") or "", *(row.get("aliases") or [])]

        for term in search_terms:
            normalized_term = normalize_search_text(term)
            if not _is_safe_alias_term(normalized_term):
                continue

            if normalized_input == normalized_term:
                alias_matches.append((2, len(normalized_term), ticker))
            elif f" {normalized_term} " in f" {normalized_input} ":
                alias_matches.append((1, len(normalized_term), ticker))

    if not alias_matches:
        return None

    alias_matches.sort(key=lambda match: (match[0], match[1]), reverse=True)
    return alias_matches[0][2]


def get_stock_info(ticker: str) -> dict[str, Any] | None:
    """Return mapping information for a resolved ticker, or None when it is unavailable."""
    if ticker is None:
        return None

    normalized_ticker = str(ticker).strip().upper().removesuffix(".JK")
    if not normalized_ticker or not re.fullmatch(r"[A-Z0-9]{2,6}", normalized_ticker):
        return None

    mapping_df = load_mapping()
    matched_rows = mapping_df[mapping_df["ticker"] == normalized_ticker]

    if matched_rows.empty:
        return None

    row = matched_rows.iloc[0]
    output_columns = REQUIRED_COLUMNS + ["stock_name", "aliases"]
    return {column: _clean_value(row[column]) for column in output_columns}


def is_stock_available(ticker: str) -> bool:
    """Return True only when ticker exists and has complete data status."""
    stock_info = get_stock_info(ticker)
    if not stock_info:
        return False

    return str(stock_info["status_data"]).strip().lower() == "lengkap"

def is_direct_ticker_input(input_text: str | None, ticker: str | None = None) -> bool:
    """
    Memeriksa apakah input pengguna hanya berupa kode saham langsung.

    Contoh input valid:
    - BBCA
    - bbca
    - BBCA.JK
    """
    if not input_text:
        return False

    raw = str(input_text).strip().upper()
    normalized = normalize_ticker(raw)
    expected = str(ticker or normalized or "").strip().upper()

    if not expected:
        return False

    return raw in {expected, f"{expected}.JK"}

def is_known_stock_identity_input(input_text: str | None, ticker: str | None = None) -> bool:
    """
    Memeriksa apakah input pengguna hanya berupa identitas saham yang dikenal,
    seperti kode ticker, nama emiten, atau alias resmi dari mapping sistem.
    """
    if not input_text or not ticker:
        return False

    stock_info = get_stock_info(ticker)
    if not stock_info:
        return False

    normalized_input = normalize_search_text(input_text)

    identity_terms = [
        stock_info.get("ticker"),
        stock_info.get("ticker_yfinance"),
        stock_info.get("stock_name"),
        *(stock_info.get("aliases") or []),
    ]

    normalized_terms = {
        normalize_search_text(term)
        for term in identity_terms
        if term
    }

    return normalized_input in normalized_terms

def validate_stock_analysis_intent(input_text: str | None, ticker: str | None = None) -> dict[str, Any]:
    """
    Memvalidasi apakah input pengguna berada dalam konteks analisis teknikal saham.

    Validasi ini mencegah sistem memproses kalimat di luar domain saham hanya karena
    terdapat kode ticker yang valid di dalam input.
    """
    if not input_text or not str(input_text).strip():
        return {
            "success": False,
            "message": "Input analisis saham belum tersedia.",
            "intent": "empty",
        }

    normalized_input = normalize_search_text(input_text)

    has_non_stock_keyword = any(
        keyword in normalized_input
        for keyword in _NON_STOCK_INTENT_KEYWORDS
    )
    if has_non_stock_keyword:
        return {
            "success": False,
            "message": INVALID_INTENT_MESSAGE,
            "intent": "non_stock_context",
        }

    if is_direct_ticker_input(input_text, ticker):
        return {
            "success": True,
            "message": "Input berupa kode saham langsung.",
            "intent": "direct_ticker",
        }

    if is_known_stock_identity_input(input_text, ticker):
        return {
            "success": True,
            "message": "Input berupa nama atau alias saham yang dikenal.",
            "intent": "stock_identity",
        }

    has_stock_keyword = any(
        keyword in normalized_input
        for keyword in _STOCK_ANALYSIS_INTENT_KEYWORDS
    )
    if has_stock_keyword:
        return {
            "success": True,
            "message": "Input berada dalam konteks analisis saham.",
            "intent": "stock_analysis_context",
        }

    return {
        "success": False,
        "message": INVALID_INTENT_MESSAGE,
        "intent": "unclear_context",
    }

def validate_stock_request(input_text: str) -> dict[str, Any]:

    
    """
    Memvalidasi input saham dari pengguna terhadap mapping dan konteks analisis.

    Fungsi ini memastikan ticker tersedia, data saham lengkap, dan kalimat pengguna
    masih berada dalam konteks analisis teknikal saham sebelum diproses lebih lanjut.
    """


    ticker = resolve_ticker(input_text) or normalize_ticker(input_text)
    stock_info = get_stock_info(ticker)

    if not stock_info:
        return {
            "success": False,
            "message": UNAVAILABLE_MESSAGE,
            "ticker": ticker,
            "ticker_yfinance": None,
            "sector": None,
            "stock_info": None,
        }

    intent_result = validate_stock_analysis_intent(input_text, stock_info["ticker"])
    if not intent_result["success"]:
        return {
            "success": False,
            "message": intent_result["message"],
            "ticker": stock_info["ticker"],
            "ticker_yfinance": stock_info["ticker_yfinance"],
            "sector": stock_info["sektor"],
            "stock_info": stock_info,
            "intent": intent_result["intent"],
        }

    if str(stock_info["status_data"]).strip().lower() != "lengkap":
        return {
            "success": False,
            "message": INCOMPLETE_DATA_MESSAGE,
            "ticker": stock_info["ticker"],
            "ticker_yfinance": stock_info["ticker_yfinance"],
            "sector": stock_info["sektor"],
            "stock_info": stock_info,
        }

    return {
        "success": True,
        "message": VALID_MESSAGE,
        "ticker": stock_info["ticker"],
        "ticker_yfinance": stock_info["ticker_yfinance"],
        "sector": stock_info["sektor"],
        "stock_info": stock_info,
    }


def _clean_value(value: Any) -> Any:
    """Convert pandas/numpy values into plain Python values for service output."""
    if isinstance(value, list):
        return [_clean_value(item) for item in value]

    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()

    if hasattr(value, "item"):
        return value.item()

    return value


def _is_safe_alias_term(term: str) -> bool:
    """Avoid short non-ticker aliases that can match unrelated prose."""
    if not term:
        return False
    return len(term) >= 3

