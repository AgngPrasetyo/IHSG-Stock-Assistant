import pandas as pd

from services.wfa_service import (
    WFA_RESULT_COLUMNS,
    aggregate_wfa_results,
    generate_wfa_windows,
    prepare_wfa_dataframe,
    run_wfa_all_indicators,
    run_wfa_for_window,
    run_wfa_pipeline,
    select_best_indicator,
    WFA_RESULT_COLUMNS,
    WFA_SELECTION_COLUMNS,
    aggregate_wfa_results,
    generate_wfa_windows,
    prepare_wfa_dataframe,
    run_wfa_all_indicators,
    run_wfa_for_window,
    run_wfa_pipeline,
    run_wfa_selection_for_window,
    run_wfa_selection_pipeline,
    select_best_indicator,
)


def make_dummy_ohlcv(periods: int = 320, start: str = "2024-10-21") -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq="D", name="Date")
    close_prices = [100.0 + (index * 0.08) + ((index % 31) - 15) * 0.35 for index in range(periods)]

    return pd.DataFrame(
        {
            "Open": [price - 0.4 for price in close_prices],
            "High": [price + 0.8 for price in close_prices],
            "Low": [price - 0.8 for price in close_prices],
            "Close": close_prices,
            "Volume": [1000 + index for index in range(periods)],
        },
        index=dates,
    )


def make_aggregate_source() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 2,
                "correct_signals": 1,
                "directional_accuracy": 50.0,
                "hit_rate": 50.0,
            },
            {
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 8,
                "correct_signals": 5,
                "directional_accuracy": 62.5,
                "hit_rate": 62.5,
            },
            {
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_active_signals": 4,
                "correct_signals": 2,
                "directional_accuracy": 50.0,
                "hit_rate": 50.0,
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


def test_prepare_wfa_dataframe_does_not_modify_original_dataframe():
    df = make_dummy_ohlcv()
    df_with_date = df.reset_index()
    original_df = df_with_date.copy(deep=True)

    prepare_wfa_dataframe(df_with_date)

    pd.testing.assert_frame_equal(df_with_date, original_df)


def test_generate_wfa_windows_returns_window_when_data_is_sufficient():
    windows = generate_wfa_windows(make_dummy_ohlcv())
    assert len(windows) >= 1


def test_each_window_has_sample_dataframes_and_combined_dataframe():
    window = generate_wfa_windows(make_dummy_ohlcv())[0]

    assert isinstance(window["in_sample_df"], pd.DataFrame)
    assert isinstance(window["out_sample_df"], pd.DataFrame)
    assert isinstance(window["combined_df"], pd.DataFrame)
    assert not window["in_sample_df"].empty
    assert not window["out_sample_df"].empty
    assert not window["combined_df"].empty


def test_out_sample_start_is_after_in_sample_end():
    window = generate_wfa_windows(make_dummy_ohlcv())[0]
    assert window["out_sample_start"] > window["in_sample_end"]


def test_combined_dataframe_contains_in_sample_and_out_sample_data():
    window = generate_wfa_windows(make_dummy_ohlcv())[0]
    expected_df = pd.concat([window["in_sample_df"], window["out_sample_df"]]).sort_index()

    pd.testing.assert_frame_equal(window["combined_df"], expected_df)


def test_generate_wfa_windows_skips_incomplete_final_out_sample_window():
    df = make_dummy_ohlcv(periods=289, start="2024-01-01")

    windows = generate_wfa_windows(df)

    assert len(windows) == 1
    assert windows[0]["in_sample_start"] == pd.Timestamp("2024-01-01")
    assert windows[0]["out_sample_start"] == pd.Timestamp("2024-07-01")
    assert windows[0]["out_sample_end"] == pd.Timestamp("2024-10-01")


def test_run_wfa_for_window_returns_three_indicator_results():
    window = generate_wfa_windows(make_dummy_ohlcv())[0]

    results = run_wfa_for_window(window, evaluation_horizons=[1, 3, 5, 10])

    assert len(results) == 3
    assert {result["indicator"] for result in results} == {"MA Crossover", "MACD", "RSI"}


def test_run_wfa_all_indicators_returns_dataframe_with_complete_columns():
    result = run_wfa_all_indicators(make_dummy_ohlcv(), evaluation_horizons=[1, 3, 5, 10])

    assert list(result.columns) == WFA_RESULT_COLUMNS


def test_aggregate_wfa_results_returns_one_row_per_indicator():
    result = aggregate_wfa_results(make_aggregate_source())

    assert len(result) == 3
    assert set(result["indicator"]) == {"MA Crossover", "MACD", "RSI"}


def test_aggregate_wfa_results_uses_sum_counts_and_average_active_window_hit_rate():
    result = aggregate_wfa_results(make_aggregate_source())
    ma_result = result[result["indicator"] == "MA Crossover"].iloc[0]

    assert ma_result["total_active_signals"] == 10
    assert ma_result["correct_signals"] == 6
    assert ma_result["directional_accuracy"] == 60.0
    assert ma_result["hit_rate"] == 56.25


def test_aggregate_wfa_results_zero_hit_rate_when_no_active_windows():
    result = aggregate_wfa_results(make_aggregate_source())
    rsi_result = result[result["indicator"] == "RSI"].iloc[0]

    assert rsi_result["total_active_signals"] == 0
    assert rsi_result["directional_accuracy"] == 0.0
    assert rsi_result["hit_rate"] == 0.0


def test_select_best_indicator_chooses_highest_directional_accuracy():
    aggregate_df = pd.DataFrame(
        [
            {
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 10,
                "correct_signals": 6,
                "directional_accuracy": 60.0,
                "hit_rate": 60.0,
            },
            {
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_active_signals": 5,
                "correct_signals": 4,
                "directional_accuracy": 80.0,
                "hit_rate": 70.0,
            },
        ]
    )

    result = select_best_indicator(aggregate_df)

    assert result["indicator"] == "MACD"


def test_select_best_indicator_uses_hit_rate_as_first_tiebreaker():
    aggregate_df = pd.DataFrame(
        [
            {
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 10,
                "correct_signals": 7,
                "directional_accuracy": 70.0,
                "hit_rate": 70.0,
            },
            {
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_active_signals": 5,
                "correct_signals": 4,
                "directional_accuracy": 70.0,
                "hit_rate": 80.0,
            },
        ]
    )

    result = select_best_indicator(aggregate_df)

    assert result["indicator"] == "MACD"


def test_select_best_indicator_uses_total_active_signals_as_second_tiebreaker():
    aggregate_df = pd.DataFrame(
        [
            {
                "indicator": "MA Crossover",
                "signal_column": "MA_Crossover_Signal",
                "total_active_signals": 10,
                "correct_signals": 7,
                "directional_accuracy": 70.0,
                "hit_rate": 70.0,
            },
            {
                "indicator": "MACD",
                "signal_column": "MACD_Trade_Signal",
                "total_active_signals": 5,
                "correct_signals": 4,
                "directional_accuracy": 70.0,
                "hit_rate": 70.0,
            },
        ]
    )

    result = select_best_indicator(aggregate_df)

    assert result["indicator"] == "MA Crossover"


def test_run_wfa_pipeline_returns_expected_keys():
    result = run_wfa_pipeline(make_dummy_ohlcv(), evaluation_horizons=[1, 3, 5, 10])

    assert set(result.keys()) == {"windows_count", "wfa_results", "aggregate_results", "best_indicator"}


def test_default_wfa_window_uses_6_3_3():
    window = generate_wfa_windows(make_dummy_ohlcv())[0]

    assert window["out_sample_start"] == window["in_sample_start"] + pd.DateOffset(months=6)
    assert window["out_sample_end"] == window["out_sample_start"] + pd.DateOffset(months=3)


def test_run_wfa_pipeline_accepts_final_evaluation_horizons():
    result = run_wfa_pipeline(
        make_dummy_ohlcv(),
        evaluation_horizons=[1, 3, 5, 10],
        in_sample_months=6,
        out_sample_months=3,
        shift_months=3,
    )

    assert result["windows_count"] >= 1
    assert not result["wfa_results"].empty
    assert not result["aggregate_results"].empty


def test_short_data_returns_safe_empty_results():
    result = run_wfa_pipeline(make_dummy_ohlcv(periods=20))

    assert result["windows_count"] == 0
    assert result["wfa_results"].empty
    assert result["aggregate_results"].empty
    assert result["best_indicator"] is None

def test_run_wfa_selection_for_window_selects_indicator_on_in_sample_then_tests_oos():
    window = generate_wfa_windows(make_dummy_ohlcv())[0]

    result = run_wfa_selection_for_window(window, evaluation_horizons=[1, 3, 5, 10])

    assert result is not None
    assert result["selected_indicator"] in {"MA Crossover", "MACD", "RSI"}
    assert result["selected_signal_column"] in {
        "MA_Crossover_Signal",
        "MACD_Trade_Signal",
        "RSI_Signal",
    }
    assert "in_sample_directional_accuracy" in result
    assert "out_sample_directional_accuracy" in result


def test_run_wfa_selection_pipeline_returns_selection_dataframe():
    result = run_wfa_selection_pipeline(
        make_dummy_ohlcv(),
        evaluation_horizons=[1, 3, 5, 10],
        in_sample_months=6,
        out_sample_months=3,
        shift_months=3,
    )

    assert set(result.keys()) == {"windows_count", "selection_results"}
    assert result["windows_count"] >= 1
    assert list(result["selection_results"].columns) == WFA_SELECTION_COLUMNS