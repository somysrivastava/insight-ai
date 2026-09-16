from datetime import datetime, timezone

import pytest

from app.services.schedule_service import compute_next_run_at


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


class TestDaily:
    def test_fires_later_today_when_hour_not_yet_passed(self):
        after = utc(2024, 6, 10, 5, 0, 0)
        result = compute_next_run_at("daily", hour=9, day_of_week=None, day_of_month=None, after=after)
        assert result == utc(2024, 6, 10, 9, 0, 0)

    def test_rolls_to_tomorrow_when_hour_already_passed(self):
        after = utc(2024, 6, 10, 14, 0, 0)
        result = compute_next_run_at("daily", hour=9, day_of_week=None, day_of_month=None, after=after)
        assert result == utc(2024, 6, 11, 9, 0, 0)

    def test_exactly_at_the_hour_rolls_to_tomorrow(self):
        # Strictly after `after` — recomputing right at the fire instant
        # must not return that same instant again.
        after = utc(2024, 6, 10, 9, 0, 0)
        result = compute_next_run_at("daily", hour=9, day_of_week=None, day_of_month=None, after=after)
        assert result == utc(2024, 6, 11, 9, 0, 0)


class TestWeekly:
    def test_fires_later_this_week_when_day_still_ahead(self):
        # 2024-06-10 is a Monday (weekday()==0); target Wednesday (2).
        after = utc(2024, 6, 10, 5, 0, 0)
        result = compute_next_run_at("weekly", hour=9, day_of_week=2, day_of_month=None, after=after)
        assert result == utc(2024, 6, 12, 9, 0, 0)

    def test_wraps_to_next_week_when_day_already_passed(self):
        # Monday, target day_of_week=0 (Monday) but hour already passed.
        after = utc(2024, 6, 10, 14, 0, 0)
        result = compute_next_run_at("weekly", hour=9, day_of_week=0, day_of_month=None, after=after)
        assert result == utc(2024, 6, 17, 9, 0, 0)

    def test_wraps_around_end_of_week(self):
        # Saturday (weekday()==5) targeting Monday (0) -> 2 days ahead.
        after = utc(2024, 6, 15, 5, 0, 0)
        result = compute_next_run_at("weekly", hour=9, day_of_week=0, day_of_month=None, after=after)
        assert result == utc(2024, 6, 17, 9, 0, 0)


class TestMonthly:
    def test_fires_later_this_month_when_day_still_ahead(self):
        after = utc(2024, 6, 1, 5, 0, 0)
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=15, after=after)
        assert result == utc(2024, 6, 15, 9, 0, 0)

    def test_rolls_to_next_month_when_day_already_passed(self):
        after = utc(2024, 6, 20, 5, 0, 0)
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=15, after=after)
        assert result == utc(2024, 7, 15, 9, 0, 0)

    def test_clamps_31_to_30_in_a_short_month(self):
        after = utc(2024, 4, 1, 5, 0, 0)
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=31, after=after)
        assert result == utc(2024, 4, 30, 9, 0, 0)

    def test_clamps_31_to_28_in_february_non_leap_year(self):
        after = utc(2023, 2, 1, 5, 0, 0)
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=31, after=after)
        assert result == utc(2023, 2, 28, 9, 0, 0)

    def test_clamps_31_to_29_in_february_leap_year(self):
        after = utc(2024, 2, 1, 5, 0, 0)
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=31, after=after)
        assert result == utc(2024, 2, 29, 9, 0, 0)

    def test_wraps_across_year_boundary(self):
        after = utc(2024, 12, 20, 5, 0, 0)
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=15, after=after)
        assert result == utc(2025, 1, 15, 9, 0, 0)

    def test_next_month_also_reclamps_when_rolling_over(self):
        # After Jan 31 (clamped from day_of_month=31), rolling to Feb in
        # a non-leap year must clamp again, to the 28th, not skip Feb.
        after = utc(2024, 1, 31, 10, 0, 0)  # already past the 9am fire
        result = compute_next_run_at("monthly", hour=9, day_of_week=None, day_of_month=31, after=after)
        assert result == utc(2024, 2, 29, 9, 0, 0)


def test_unsupported_frequency_raises():
    with pytest.raises(ValueError, match="Unsupported frequency"):
        compute_next_run_at("yearly", hour=9, day_of_week=None, day_of_month=None)


def test_defaults_after_to_now_when_omitted():
    result = compute_next_run_at("daily", hour=0, day_of_week=None, day_of_month=None)
    assert result.tzinfo is not None
    assert result > datetime.now(timezone.utc)
