from services.mapping_service import (
    get_stock_info,
    is_stock_available,
    load_mapping,
    normalize_ticker,
    validate_stock_request,
    validate_stock_analysis_intent,
    resolve_ticker,
)


def test_load_mapping_reads_file():
    mapping_df = load_mapping()

    assert not mapping_df.empty
    assert "ticker" in mapping_df.columns
    assert "ticker_yfinance" in mapping_df.columns
    assert "stock_name" in mapping_df.columns
    assert "aliases" in mapping_df.columns


def test_normalize_ticker_lowercase():
    assert normalize_ticker("bbca") == "BBCA"


def test_normalize_ticker_yfinance_suffix():
    assert normalize_ticker("BBCA.JK") == "BBCA"


def test_normalize_ticker_sentence():
    assert normalize_ticker("Analisis saham BBCA") == "BBCA"


def test_get_stock_info_returns_bbca_data():
    stock_info = get_stock_info("BBCA")

    assert stock_info is not None
    assert stock_info["ticker"] == "BBCA"
    assert stock_info["ticker_yfinance"] == "BBCA.JK"
    assert stock_info["stock_name"] == "Bank Central Asia"
    assert "bank bca" in stock_info["aliases"]


def test_is_stock_available_for_complete_data():
    assert is_stock_available("BBCA") is True


def test_validate_stock_request_success():
    result = validate_stock_request("Analisis saham BBCA")

    assert result["success"] is True
    assert result["message"] == "Kode saham valid dan tersedia dalam mapping sistem."
    assert result["ticker"] == "BBCA"
    assert result["ticker_yfinance"] == "BBCA.JK"


def test_validate_stock_request_alias_bank_bca_sentence():
    result = validate_stock_request("analisis bank bca")

    assert result["success"] is True
    assert result["ticker"] == "BBCA"


def test_validate_stock_request_company_name_bank_central_asia():
    result = validate_stock_request("Bank Central Asia")

    assert result["success"] is True
    assert result["ticker"] == "BBCA"


def test_validate_stock_request_alias_bank_mandiri_sentence():
    result = validate_stock_request("analisis bank mandiri")

    assert result["success"] is True
    assert result["ticker"] == "BMRI"


def test_validate_stock_request_alias_goto_sentence():
    result = validate_stock_request("analisis goto")

    assert result["success"] is True
    assert result["ticker"] == "GOTO"


def test_validate_stock_request_alias_perusahaan_gas_negara():
    result = validate_stock_request("perusahaan gas negara")

    assert result["success"] is True
    assert result["ticker"] == "PGAS"


def test_validate_stock_request_unavailable_ticker():
    result = validate_stock_request("Analisis saham XXX")

    assert result["success"] is False
    assert result["message"] == "Kode saham belum tersedia dalam mapping sistem."

def test_validate_stock_analysis_intent_accepts_direct_ticker():
    result = validate_stock_analysis_intent("BBCA", "BBCA")

    assert result["success"] is True
    assert result["intent"] == "direct_ticker"


def test_validate_stock_analysis_intent_accepts_stock_context():
    result = validate_stock_analysis_intent("analisis saham BBCA", "BBCA")

    assert result["success"] is True
    assert result["intent"] == "stock_analysis_context"


def test_validate_stock_analysis_intent_rejects_health_context():
    result = validate_stock_analysis_intent(
        "saya ingin bertanya mengenai riwayat kesehatan BBCA",
        "BBCA",
    )

    assert result["success"] is False
    assert result["intent"] == "non_stock_context"
    assert "Input belum sesuai" in result["message"]
    assert "konteks analisis teknikal saham" in result["message"]


def test_validate_stock_request_rejects_health_context():
    result = validate_stock_request("saya ingin bertanya mengenai riwayat kesehatan BBCA")

    assert result["success"] is False
    assert result["ticker"] == "BBCA"
    assert result["intent"] == "non_stock_context"

def test_validate_stock_analysis_intent_accepts_company_name_identity():
    result = validate_stock_analysis_intent("Bank Central Asia", "BBCA")

    assert result["success"] is True
    assert result["intent"] == "stock_identity"


def test_validate_stock_analysis_intent_accepts_alias_identity():
    result = validate_stock_analysis_intent("perusahaan gas negara", "PGAS")

    assert result["success"] is True
    assert result["intent"] == "stock_identity"


def test_validate_stock_analysis_intent_accepts_check_keyword():
    result = validate_stock_analysis_intent("Tolong cek ADMR", "ADMR")

    assert result["success"] is True
    assert result["intent"] == "stock_analysis_context"

def test_validate_stock_analysis_intent_rejects_food_context():
    result = validate_stock_analysis_intent("saya ingin makan BBCA", "BBCA")

    assert result["success"] is False
    assert result["intent"] == "non_stock_context"


def test_validate_stock_analysis_intent_rejects_taste_context():
    result = validate_stock_analysis_intent("cek rasa BBCA", "BBCA")

    assert result["success"] is False
    assert result["intent"] == "non_stock_context"


def test_resolve_ticker_prefers_known_ticker_inside_sentence():
    result = resolve_ticker("saya ingin menganalisis saham bbca apakah itu enak")

    assert result == "BBCA"


def test_validate_stock_request_rejects_stock_sentence_with_food_context():
    result = validate_stock_request("saya ingin menganalisis saham bbca apakah itu enak")

    assert result["success"] is False
    assert result["ticker"] == "BBCA"
    assert result["intent"] == "non_stock_context"