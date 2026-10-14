"""Filing/deposit due dates. Weekends roll to Monday; federal and NY holidays are
NOT handled — check the agency calendar. Deposit schedule assumes a MONTHLY
federal depositor; semiweekly depositors and NYS-1 schedules are not modeled yet.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta


def roll_weekend(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def quarter_end_due(year: int, quarter: int) -> date:
    """Last day of the month after quarter end (941, NYS-45)."""
    y, m = (year, quarter * 3 + 1) if quarter < 4 else (year + 1, 1)
    return roll_weekend(_month_end(y, m))


def year_deadlines(year: int) -> list[tuple[date, str]]:
    items: list[tuple[date, str]] = []
    for m in range(1, 13):
        y, mm = (year, m + 1) if m < 12 else (year + 1, 1)
        items.append((roll_weekend(date(y, mm, 15)),
                      f"Federal tax deposit (monthly depositor) for {calendar.month_name[m]} {year} wages"))
    for q in range(1, 5):
        due = quarter_end_due(year, q)
        items.append((due, f"Form 941 for Q{q} {year}"))
        items.append((due, f"NYS-45 for Q{q} {year}"))
    jan31 = roll_weekend(date(year + 1, 1, 31))
    items += [(jan31, f"Form 940 for {year}"), (jan31, f"W-2/W-3 for {year} (SSA)"),
              (jan31, f"1099-NEC for {year} (recipient copy + IRS)")]
    return sorted(items)
