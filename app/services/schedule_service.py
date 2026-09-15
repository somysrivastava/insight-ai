# WHY THIS FILE EXISTS:
# Computing "when does this schedule next fire" is the one genuinely
# fiddly piece of Day 19 — calendar month-length handling for monthly
# schedules, and making sure "next" always means strictly after `after`
# (so recomputing right at the fire time doesn't return the same
# instant again). Isolated here so app/tasks/scheduled_tasks.py and the
# schedules router (create/update) both call the same logic instead of
# each reimplementing it slightly differently.

import calendar
from datetime import datetime, timedelta, timezone


def compute_next_run_at(
    frequency: str,
    hour: int,
    day_of_week: int | None,
    day_of_month: int | None,
    after: datetime | None = None,
) -> datetime:
    """
    Returns the next UTC datetime, strictly after `after` (defaults to
    now), matching the given schedule.

    Monthly: day_of_month is clamped to the real last day of whichever
    month is being considered — day_of_month=31 fires every month, on
    the 28th/29th/30th/31st depending on that month's actual length,
    rather than skipping months that don't have a 31st.
    """
    after = after or datetime.now(timezone.utc)

    if frequency == "daily":
        candidate = after.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate

    if frequency == "weekly":
        candidate = after.replace(hour=hour, minute=0, second=0, microsecond=0)
        days_ahead = (day_of_week - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= after:
            candidate += timedelta(days=7)
        return candidate

    if frequency == "monthly":
        candidate = _monthly_candidate(after.year, after.month, day_of_month, hour)
        if candidate <= after:
            year, month = after.year, after.month + 1
            if month > 12:
                year, month = year + 1, 1
            candidate = _monthly_candidate(year, month, day_of_month, hour)
        return candidate

    raise ValueError(f"Unsupported frequency: {frequency}")


def _monthly_candidate(year: int, month: int, day_of_month: int, hour: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    day = min(day_of_month, last_day)
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)
