from services.technical_hint_service import get_indicator_hint


def _terms_and_text(indicator):
    hint = get_indicator_hint(indicator)
    terms = {item["term"] for item in hint["items"]}
    text = " ".join(
        [hint["title"], hint["indicator"], *[item["term"] for item in hint["items"]], *[item["description"] for item in hint["items"]]]
    )
    return terms, text


def test_ma_crossover_hint_contains_only_ma_terms():
    terms, text = _terms_and_text("MA Crossover")

    assert {"MA Crossover", "SMA20", "SMA50"}.issubset(terms)
    assert "RSI" not in text
    assert "MACD" not in text


def test_rsi_hint_contains_rsi_terms_without_other_indicator_terms():
    terms, text = _terms_and_text("RSI")

    assert {"RSI", "Overbought", "Oversold"}.issubset(terms)
    assert "MACD" not in text
    assert "SMA20" not in text
    assert "SMA50" not in text


def test_macd_hint_contains_macd_terms_without_other_indicator_terms():
    terms, text = _terms_and_text("MACD")

    assert {"MACD Line", "Signal Line"}.issubset(terms)
    assert "RSI" not in text
    assert "SMA20" not in text
    assert "SMA50" not in text


def test_unknown_indicator_returns_safe_dict():
    hint = get_indicator_hint("unknown")

    assert isinstance(hint, dict)
    assert hint["title"] == "Hint istilah teknikal"
    assert hint["indicator"] == "unknown"
    assert hint["items"] == []
