import pandas as pd
import pytest

from app.services.kpi_service import compute_kpis


def test_basic_counts_and_completeness():
    df = pd.DataFrame({"a": [1, 2, None], "b": [4, 5, 6]})
    kpis = compute_kpis(df)

    assert kpis["total_records"] == 3
    assert kpis["total_columns"] == 2
    assert kpis["missing_cells"] == 1
    # 5 of 6 cells present -> 83.33%
    assert kpis["data_completeness_pct"] == pytest.approx(83.33, abs=0.01)


def test_empty_dataframe_does_not_divide_by_zero():
    df = pd.DataFrame({"a": [], "b": []})
    kpis = compute_kpis(df)
    assert kpis["total_records"] == 0
    assert kpis["data_completeness_pct"] == 0.0


def test_duplicate_records_counted():
    df = pd.DataFrame({"a": [1, 1, 2], "b": [4, 4, 5]})
    kpis = compute_kpis(df)
    assert kpis["duplicate_records"] == 1


def test_primary_metric_prefers_value_keyword_column():
    df = pd.DataFrame({"id": [1, 2, 3], "revenue": [100.0, 200.0, 300.0]})
    kpis = compute_kpis(df)
    assert kpis["primary_metric_column"] == "revenue"
    assert kpis["total_value"] == 600.0
    assert kpis["average_value"] == 200.0
    assert kpis["median_value"] == 200.0
    assert kpis["max_value"] == 300.0
    assert kpis["min_value"] == 100.0


def test_primary_metric_falls_back_to_first_numeric_when_no_keyword_matches():
    df = pd.DataFrame({"score": [10.0, 20.0], "count": [1, 2]})
    kpis = compute_kpis(df)
    assert kpis["primary_metric_column"] == "score"


def test_no_numeric_columns_skips_value_kpis():
    df = pd.DataFrame({"name": ["a", "b"], "category": ["x", "y"]})
    kpis = compute_kpis(df)
    assert "primary_metric_column" not in kpis
    assert "total_value" not in kpis


def test_coeff_of_variation_skipped_when_mean_is_zero():
    df = pd.DataFrame({"revenue": [-5.0, 5.0]})
    kpis = compute_kpis(df)
    assert kpis["average_value"] == 0.0
    assert "coeff_of_variation" not in kpis


def test_high_value_threshold_is_75th_percentile():
    df = pd.DataFrame({"revenue": [10.0, 20.0, 30.0, 40.0]})
    kpis = compute_kpis(df)
    assert kpis["high_value_threshold"] == pytest.approx(32.5)
    assert kpis["high_value_records"] == 1


def test_explicit_datetime_column_drives_date_range():
    df = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2024-01-01", "2024-03-01", "2024-02-01"]),
            "revenue": [100.0, 200.0, 300.0],
        }
    )
    kpis = compute_kpis(df)
    assert kpis["date_column"] == "order_date"
    assert kpis["date_range_start"] == "2024-01-01"
    assert kpis["date_range_end"] == "2024-03-01"
    assert kpis["reporting_period_days"] == 60


def test_string_column_auto_parsed_as_date_when_mostly_valid():
    df = pd.DataFrame(
        {
            "order_date": ["2024-01-01", "2024-02-01", "2024-03-01", "not-a-date"],
            "revenue": [100.0, 200.0, 300.0, 400.0],
        }
    )
    kpis = compute_kpis(df)
    assert kpis["date_column"] == "order_date"


def test_string_column_not_parsed_when_mostly_invalid():
    df = pd.DataFrame({"note": ["hello", "world", "foo", "bar"], "revenue": [1.0, 2.0, 3.0, 4.0]})
    kpis = compute_kpis(df)
    assert "date_column" not in kpis


def test_mom_growth_computed_across_two_months():
    df = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10"]),
            "revenue": [100.0, 100.0, 300.0],
        }
    )
    kpis = compute_kpis(df)
    # Jan total = 200, Feb total = 300 -> +50%
    assert kpis["mom_growth_pct"] == pytest.approx(50.0)


def test_segment_column_picked_from_low_cardinality_categorical():
    df = pd.DataFrame(
        {
            "region": ["West", "East", "West", "East", "North"],
            "revenue": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    kpis = compute_kpis(df)
    assert kpis["primary_segment_column"] == "region"
    assert kpis["segment_count"] == 3


def test_segment_column_skipped_when_cardinality_too_high_or_too_low():
    # Segment eligibility is 2 < nunique < 50, evaluated on fixed
    # thresholds only (not relative to row count) — "flag" has just 1
    # distinct value (excluded, needs > 2) and "id" has 60 distinct
    # values (excluded, needs < 50).
    df = pd.DataFrame(
        {
            "id": [f"id-{i}" for i in range(60)],
            "flag": ["x"] * 60,
            "revenue": [float(i) for i in range(60)],
        }
    )
    kpis = compute_kpis(df)
    assert "primary_segment_column" not in kpis
