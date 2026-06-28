import pandas as pd

from services import sector_service
from services.sector_service import (
    SECTOR_AGGREGATE_COLUMNS,
    SECTOR_RESULT_COLUMNS,
    aggregate_sector_results,
    get_available_sectors,
    get_sector_stocks,
    run_all_sectors_pipeline,
    run_sector_pipeline,
    run_sector_wfa,
    run_wfa_for_stock_row,
    select_best_sector_indicator,
)


def make_mapping_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "BBCA",
                "ticker_yfinance": "BBCA.JK",
                "sektor": "Finansial",
                "is_sample": "Ya",
                "status_data": "Lengkap",
            },
            {
                "ticker": "BBRI",
                "ticker_yfinance": "BBRI.JK",
                "sektor": "Finansial",
                "is_sample": "Ya",
                "status_data": "Lengkap",
            },
            {
                "ticker": "ASII",
                "ticker_yfinance": "ASII.JK",
                "sektor": "Industri",
                "is_sample": "Ya",
                "status_data": "Lengkap",
            },
            {
                "ticker": "GOTO",
                "ticker_yfinance": "GOTO.JK",
                "sektor": "Teknologi",
                "is_sample": "Tidak",
                "status_data": "Lengkap",
            },
            {
                "ticker": "ADRO",
                "ticker_yfinance": "ADRO.JK",
                "sektor": "Energi",
                "is_sample": "Ya",
                "status_data": "Tidak Lengkap",
            },
        ]
    )


def make_price_df() -> pd.DataFrame:
    dates = pd.date_range("2024-10-21", periods=10, freq="D", name="Date")
    return pd.DataFrame(
        {
            "Open": range(10),
            "High": range(1, 11),
            "Low": range(10),
            "Close": range(10),
            "Volume": range(100, 110),
        },
        index=dates,
    )


def make_stock_aggregate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 4,
                "correct_signals": 3,
                "directional_accuracy": 75.0,
                "hit_rate": 75.0,
            },
            {
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_active_signals": 5,
                "correct_signals": 2,
                "directional_accuracy": 40.0,
                "hit_rate": 40.0,
            },
            {
                "indicator": "RSI",
                "signal_column": "RSI_Signal",
                "total_active_signals": 0,
                "correct_signals": 0,
                "directional_accuracy": 0.0,
                "hit_rate": 0.0,
            },
        ]
    )


def make_sector_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "sektor": "Finansial",
                "ticker": "BBCA",
                "ticker_yfinance": "BBCA.JK",
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 2,
                "correct_signals": 1,
                "directional_accuracy": 50.0,
                "hit_rate": 50.0,
                "windows_count": 6,
            },
            {
                "sektor": "Finansial",
                "ticker": "BBRI",
                "ticker_yfinance": "BBRI.JK",
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 8,
                "correct_signals": 5,
                "directional_accuracy": 62.5,
                "hit_rate": 62.5,
                "windows_count": 6,
            },
            {
                "sektor": "Finansial",
                "ticker": "BBCA",
                "ticker_yfinance": "BBCA.JK",
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_active_signals": 4,
                "correct_signals": 2,
                "directional_accuracy": 50.0,
                "hit_rate": 50.0,
                "windows_count": 6,
            },
        ]
    )


def test_get_available_sectors_returns_unique_complete_sample_sectors():
    result = get_available_sectors(make_mapping_df())

    assert result == ["Finansial", "Industri"]


def test_get_sector_stocks_returns_only_requested_sector():
    result = get_sector_stocks("Finansial", make_mapping_df())

    assert len(result) == 2
    assert set(result["ticker"]) == {"BBCA", "BBRI"}
    assert list(result.columns) == ["ticker", "ticker_yfinance", "sektor"]


def test_get_sector_stocks_returns_empty_dataframe_when_sector_not_found():
    result = get_sector_stocks("Kesehatan", make_mapping_df())

    assert result.empty
    assert list(result.columns) == ["ticker", "ticker_yfinance", "sektor"]


def test_run_wfa_for_stock_row_adds_stock_identity_columns(monkeypatch):
    monkeypatch.setattr(sector_service, "load_or_fetch_price_data", lambda ticker: make_price_df())
    monkeypatch.setattr(
        sector_service,
        "run_wfa_pipeline",
        lambda df, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3: {
            "windows_count": 6,
            "aggregate_results": make_stock_aggregate(),
        },
    )

    result = run_wfa_for_stock_row(make_mapping_df().iloc[0])

    assert list(result.columns) == SECTOR_RESULT_COLUMNS
    assert set(result["ticker"]) == {"BBCA"}
    assert set(result["ticker_yfinance"]) == {"BBCA.JK"}
    assert set(result["sektor"]) == {"Finansial"}
    assert set(result["windows_count"]) == {6}


def test_run_sector_wfa_combines_multiple_stock_results(monkeypatch):
    monkeypatch.setattr(
        sector_service,
        "get_sector_stocks",
        lambda sector: get_sector_stocks(sector, make_mapping_df()),
    )
    monkeypatch.setattr(sector_service, "load_or_fetch_price_data", lambda ticker: make_price_df())
    monkeypatch.setattr(
        sector_service,
        "run_wfa_pipeline",
        lambda df, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3: {
            "windows_count": 6,
            "aggregate_results": make_stock_aggregate(),
        },
    )

    result = run_sector_wfa("Finansial")

    assert len(result) == 6
    assert set(result["ticker"]) == {"BBCA", "BBRI"}


def test_aggregate_sector_results_sums_total_active_and_correct_signals():
    result = aggregate_sector_results(make_sector_results())
    ma_result = result[result["indicator"] == "MA Crossover"].iloc[0]

    assert ma_result["total_active_signals"] == 10
    assert ma_result["correct_signals"] == 6


def test_aggregate_sector_results_does_not_average_percentages():
    result = aggregate_sector_results(make_sector_results())
    ma_result = result[result["indicator"] == "MA Crossover"].iloc[0]

    assert ma_result["directional_accuracy"] == 60.0
    assert ma_result["hit_rate"] == 60.0


def test_aggregate_sector_results_returns_one_row_per_indicator():
    result = aggregate_sector_results(make_sector_results())

    assert list(result.columns) == SECTOR_AGGREGATE_COLUMNS
    assert len(result) == 2
    assert set(result["indicator"]) == {"MA Crossover", "MACD"}


def test_select_best_sector_indicator_chooses_highest_directional_accuracy():
    aggregate_df = pd.DataFrame(
        [
            {
                "sektor": "Finansial",
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_stocks": 2,
                "total_windows": 12,
                "total_active_signals": 10,
                "correct_signals": 6,
                "directional_accuracy": 60.0,
                "hit_rate": 60.0,
            },
            {
                "sektor": "Finansial",
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_stocks": 2,
                "total_windows": 12,
                "total_active_signals": 5,
                "correct_signals": 4,
                "directional_accuracy": 80.0,
                "hit_rate": 70.0,
            },
        ]
    )

    result = select_best_sector_indicator(aggregate_df)

    assert result["indicator"] == "MACD"


def test_select_best_sector_indicator_uses_hit_rate_as_first_tiebreaker():
    aggregate_df = pd.DataFrame(
        [
            {
                "sektor": "Finansial",
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_stocks": 2,
                "total_windows": 12,
                "total_active_signals": 10,
                "correct_signals": 7,
                "directional_accuracy": 70.0,
                "hit_rate": 70.0,
            },
            {
                "sektor": "Finansial",
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_stocks": 2,
                "total_windows": 12,
                "total_active_signals": 5,
                "correct_signals": 4,
                "directional_accuracy": 70.0,
                "hit_rate": 80.0,
            },
        ]
    )

    result = select_best_sector_indicator(aggregate_df)

    assert result["indicator"] == "MACD"


def test_select_best_sector_indicator_uses_total_active_signals_as_second_tiebreaker():
    aggregate_df = pd.DataFrame(
        [
            {
                "sektor": "Finansial",
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_stocks": 2,
                "total_windows": 12,
                "total_active_signals": 10,
                "correct_signals": 7,
                "directional_accuracy": 70.0,
                "hit_rate": 70.0,
            },
            {
                "sektor": "Finansial",
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_stocks": 2,
                "total_windows": 12,
                "total_active_signals": 5,
                "correct_signals": 4,
                "directional_accuracy": 70.0,
                "hit_rate": 70.0,
            },
        ]
    )

    result = select_best_sector_indicator(aggregate_df)

    assert result["indicator"] == "MA Crossover"


def test_run_sector_pipeline_returns_expected_keys(monkeypatch):
    monkeypatch.setattr(
        sector_service,
        "get_sector_stocks",
        lambda sector: get_sector_stocks(sector, make_mapping_df()),
    )
    monkeypatch.setattr(
        sector_service,
        "run_sector_wfa",
        lambda sector, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3: make_sector_results(),
    )

    result = run_sector_pipeline("Finansial")

    assert set(result.keys()) == {
        "sector",
        "stocks_count",
        "sector_results",
        "sector_aggregate",
        "best_indicator",
    }
    assert result["sector"] == "Finansial"
    assert result["stocks_count"] == 2


def test_run_sector_pipeline_accepts_evaluation_horizon_three(monkeypatch):
    captured_horizons = []

    monkeypatch.setattr(
        sector_service,
        "get_sector_stocks",
        lambda sector: get_sector_stocks(sector, make_mapping_df()),
    )
    monkeypatch.setattr(sector_service, "load_or_fetch_price_data", lambda ticker: make_price_df())

    def fake_run_wfa_pipeline(df, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3):
        captured_horizons.append(evaluation_horizon_periods)
        return {"windows_count": 6, "aggregate_results": make_stock_aggregate()}

    monkeypatch.setattr(sector_service, "run_wfa_pipeline", fake_run_wfa_pipeline)

    result = run_sector_pipeline("Finansial", evaluation_horizon_periods=3)

    assert result["stocks_count"] == 2
    assert captured_horizons == [3, 3]
    assert result["best_indicator"] is not None


def test_run_all_sectors_pipeline_returns_all_sectors(monkeypatch):
    monkeypatch.setattr(sector_service, "get_available_sectors", lambda: ["Finansial", "Industri"])
    monkeypatch.setattr(
        sector_service,
        "run_sector_pipeline",
        lambda sector, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3: {
            "sector": sector,
            "best_indicator": {"indicator": "MACD"},
        },
    )

    result = run_all_sectors_pipeline()

    assert result["sectors_count"] == 2
    assert result["sectors"] == ["Finansial", "Industri"]
    assert set(result["results_by_sector"]) == {"Finansial", "Industri"}


def test_sector_pipeline_stays_safe_when_one_stock_fails(monkeypatch):
    monkeypatch.setattr(
        sector_service,
        "get_sector_stocks",
        lambda sector: get_sector_stocks(sector, make_mapping_df()),
    )

    def fake_run_wfa_for_stock_row(stock_row, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3):
        if stock_row["ticker"] == "BBRI":
            return pd.DataFrame(columns=SECTOR_RESULT_COLUMNS)
        result = make_stock_aggregate().copy()
        result["ticker"] = stock_row["ticker"]
        result["ticker_yfinance"] = stock_row["ticker_yfinance"]
        result["sektor"] = stock_row["sektor"]
        result["windows_count"] = 6
        return result[SECTOR_RESULT_COLUMNS]

    monkeypatch.setattr(sector_service, "run_wfa_for_stock_row", fake_run_wfa_for_stock_row)

    result = run_sector_pipeline("Finansial")

    assert result["stocks_count"] == 2
    assert set(result["sector_results"]["ticker"]) == {"BBCA"}
    assert result["best_indicator"] is not None




def test_sector_service_forwards_final_wfa_parameters(monkeypatch):
    captured = []
    monkeypatch.setattr(sector_service, "get_sector_stocks", lambda sector: get_sector_stocks(sector, make_mapping_df()))
    monkeypatch.setattr(sector_service, "load_or_fetch_price_data", lambda ticker: make_price_df())

    def fake_run_wfa_pipeline(df, evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3):
        captured.append((evaluation_horizon_periods, in_sample_months, out_sample_months, shift_months))
        return {"windows_count": 4, "aggregate_results": make_stock_aggregate()}

    monkeypatch.setattr(sector_service, "run_wfa_pipeline", fake_run_wfa_pipeline)
    result = run_sector_pipeline("Finansial", evaluation_horizon_periods=3, in_sample_months=6, out_sample_months=3, shift_months=3)

    assert result["best_indicator"] is not None
    assert captured == [(3, 6, 3, 3), (3, 6, 3, 3)]
