import pytest
import pandas as pd

from services.metric_service import (
    AVERAGE_FORWARD_RETURN_COLUMN,
    calculate_actual_direction,
    calculate_average_actual_direction,
    calculate_average_forward_return,
    calculate_directional_accuracy,
    calculate_forward_return,
    calculate_hit_rate,
    evaluate_all_signal_columns,
    evaluate_all_signal_columns_average_forward,
    evaluate_signal_performance,
    evaluate_signal_performance_average_forward,
)


def make_metric_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [100.0, 110.0, 100.0, 105.0, 105.0],
            "MA_Crossover_Signal": ["BUY", "SELL", "SELL", "HOLD", "BUY"],
            "MACD_Trade_Signal": ["HOLD", "BUY", "SELL", "HOLD", "SELL"],
            "RSI_Signal": ["BUY", "HOLD", "SELL", "HOLD", "HOLD"],
        },
        index=pd.date_range("2024-10-21", periods=5, freq="D", name="Date"),
    )


def make_average_forward_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [100.0, 110.0, 90.0, 120.0, 130.0, 80.0, 150.0, 70.0, 160.0, 60.0, 170.0, 50.0],
            "MA_Crossover_Signal": ["BUY", "SELL", "BUY", "SELL", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD"],
            "MACD_Trade_Signal": ["HOLD"] * 12,
            "RSI_Signal": ["HOLD"] * 12,
        },
        index=pd.date_range("2026-01-01", periods=12, freq="D", name="Date"),
    )


def test_calculate_forward_return_adds_forward_return_column():
    result = calculate_forward_return(make_metric_df())
    assert "Forward_Return" in result.columns


def test_forward_periods_one_keeps_previous_next_close_behavior():
    result = calculate_forward_return(make_metric_df(), forward_periods=1)
    assert result["Forward_Return"].iloc[0] == pytest.approx(0.1)


def test_forward_periods_three_uses_close_three_rows_ahead():
    result = calculate_forward_return(make_metric_df(), forward_periods=3)
    assert result["Forward_Return"].iloc[0] == pytest.approx(0.05)


def test_calculate_actual_direction_adds_actual_direction_column():
    result = calculate_actual_direction(make_metric_df())
    assert "Actual_Direction" in result.columns


def test_average_forward_return_uses_t1_t3_t5_t10_and_requires_all_horizons():
    result = calculate_average_forward_return(make_average_forward_df(), forward_horizons=[1, 3, 5, 10])
    expected_first = ((110 - 100) / 100 + (120 - 100) / 100 + (80 - 100) / 100 + (170 - 100) / 100) / 4

    assert AVERAGE_FORWARD_RETURN_COLUMN in result.columns
    assert result[AVERAGE_FORWARD_RETURN_COLUMN].iloc[0] == pytest.approx(expected_first)
    assert pd.isna(result[AVERAGE_FORWARD_RETURN_COLUMN].iloc[2])


def test_average_actual_direction_uses_average_forward_return():
    result = calculate_average_actual_direction(make_average_forward_df(), forward_horizons=[1, 3, 5, 10])

    assert result["Actual_Direction"].iloc[0] == "UP"
    assert result["Actual_Direction"].iloc[1] == "DOWN"
    assert result["Actual_Direction"].iloc[2] == "UNKNOWN"


def test_average_forward_buy_and_sell_correctness():
    result = evaluate_signal_performance_average_forward(
        make_average_forward_df(),
        "MA_Crossover_Signal",
        forward_horizons=[1, 3, 5, 10],
    )

    assert result["evaluation_method"] == "average_forward_return"
    assert result["forward_horizons"] == "1,3,5,10"
    assert result["total_active_signals"] == 2
    assert result["correct_signals"] == 2
    assert result["directional_accuracy"] == 100.0


def test_average_forward_last_rows_are_not_evaluated_when_any_horizon_missing():
    df = make_average_forward_df()
    df.loc[df.index[2], "MA_Crossover_Signal"] = "BUY"

    result = evaluate_signal_performance_average_forward(df, "MA_Crossover_Signal", forward_horizons=[1, 3, 5, 10])

    assert result["total_active_signals"] == 2


def test_buy_is_wrong_when_next_close_goes_down_single_horizon_compatibility():
    df = pd.DataFrame(
        {"Close": [100.0, 90.0], "MA_Crossover_Signal": ["BUY", "HOLD"]},
        index=pd.date_range("2024-10-21", periods=2, freq="D", name="Date"),
    )

    result = evaluate_signal_performance(df, "MA_Crossover_Signal")

    assert result["total_active_signals"] == 1
    assert result["correct_signals"] == 0


def test_sell_is_correct_when_next_close_goes_down_single_horizon_compatibility():
    df = pd.DataFrame(
        {"Close": [100.0, 90.0], "MA_Crossover_Signal": ["SELL", "HOLD"]},
        index=pd.date_range("2024-10-21", periods=2, freq="D", name="Date"),
    )

    result = evaluate_signal_performance(df, "MA_Crossover_Signal")

    assert result["total_active_signals"] == 1
    assert result["correct_signals"] == 1


def test_hold_is_not_counted_as_active_signal():
    df = pd.DataFrame(
        {"Close": [100.0, 110.0, 120.0], "MA_Crossover_Signal": ["HOLD", "BUY", "HOLD"]},
        index=pd.date_range("2024-10-21", periods=3, freq="D", name="Date"),
    )

    result = evaluate_signal_performance(df, "MA_Crossover_Signal")

    assert result["total_active_signals"] == 1


def test_last_row_is_not_evaluated():
    df = pd.DataFrame(
        {"Close": [100.0, 110.0], "MA_Crossover_Signal": ["HOLD", "BUY"]},
        index=pd.date_range("2024-10-21", periods=2, freq="D", name="Date"),
    )

    result = evaluate_signal_performance(df, "MA_Crossover_Signal")

    assert result["total_active_signals"] == 0


def test_evaluate_signal_performance_returns_expected_counts_single_horizon_compatibility():
    result = evaluate_signal_performance(make_metric_df(), "MA_Crossover_Signal")

    assert result["total_active_signals"] == 3
    assert result["correct_signals"] == 2


def test_directional_accuracy_is_percentage_single_horizon_compatibility():
    accuracy = calculate_directional_accuracy(make_metric_df(), "MA_Crossover_Signal")

    assert accuracy == pytest.approx((2 / 3) * 100)


def test_hit_rate_is_percentage_single_horizon_compatibility():
    hit_rate = calculate_hit_rate(make_metric_df(), "MA_Crossover_Signal")

    assert hit_rate == pytest.approx((2 / 3) * 100)


def test_metrics_are_zero_when_no_active_signals():
    df = pd.DataFrame(
        {"Close": [100.0, 110.0, 120.0], "MA_Crossover_Signal": ["HOLD", "HOLD", "HOLD"]},
        index=pd.date_range("2024-10-21", periods=3, freq="D", name="Date"),
    )

    result = evaluate_signal_performance(df, "MA_Crossover_Signal")

    assert result["directional_accuracy"] == 0.0
    assert result["hit_rate"] == 0.0


def test_evaluate_all_signal_columns_average_forward_returns_available_signal_results():
    df = make_average_forward_df()[["Close", "MA_Crossover_Signal", "RSI_Signal"]]

    result = evaluate_all_signal_columns_average_forward(df, forward_horizons=[1, 3, 5, 10])

    assert len(result) == 2
    assert {item["signal_column"] for item in result} == {"MA_Crossover_Signal", "RSI_Signal"}


def test_evaluate_all_signal_columns_single_horizon_compatibility():
    df = make_metric_df()[["Close", "MA_Crossover_Signal", "RSI_Signal"]]

    result = evaluate_all_signal_columns(df)

    assert len(result) == 2
    assert {item["signal_column"] for item in result} == {"MA_Crossover_Signal", "RSI_Signal"}


def test_metric_functions_do_not_modify_original_dataframe():
    df = make_metric_df()
    original_df = df.copy(deep=True)

    evaluate_signal_performance_average_forward(df, "MA_Crossover_Signal")

    pd.testing.assert_frame_equal(df, original_df)
