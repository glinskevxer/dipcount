"""Walking the clock rather than testing one day of it.

Every date bug this package could have is invisible on the day the test was
written. A window that loses an hour does it twice a year, a week number that
slips does it in the last days of December, and a degree day method that goes
negative does it on one cold night in April. So these walk whole years rather
than picking a day, and they walk the two days a year the offset changes on
purpose.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from itertools import pairwise

import pytest

from dipcount import clock
from dipcount.model.weather import AVERAGE, MODIFIED, SINE, degree_days
from dipcount.store import window

YEARS = range(2015, 2041)
SPRING_FORWARD = dt.date(2025, 3, 9)
FALL_BACK = dt.date(2025, 11, 2)


def every_day(first: int, last: int) -> list[dt.date]:
    """Every day between two years, inclusive."""
    out: list[dt.date] = []
    at = dt.date(first, 1, 1)
    end = dt.date(last, 12, 31)
    while at <= end:
        out.append(at)
        at += dt.timedelta(days=1)
    return out


def test_every_day_of_a_decade_lands_in_exactly_one_week() -> None:
    for day in every_day(2020, 2030):
        year, number = clock.epi_week(day)
        assert clock.week_start(year, number) <= day <= clock.week_end(year, number)


def test_the_weeks_of_every_year_tile_it_without_a_gap() -> None:
    for year in YEARS:
        weeks = clock.weeks_in_year(year)
        for number in range(1, weeks):
            assert clock.week_end(year, number) + dt.timedelta(days=1) == clock.week_start(
                year,
                number + 1,
            )


def test_the_last_week_of_a_year_runs_into_the_first_of_the_next() -> None:
    for year in YEARS:
        last = clock.week_end(year, clock.weeks_in_year(year))
        assert last + dt.timedelta(days=1) == clock.week_start(year + 1, 1)


def test_every_year_has_fifty_two_or_fifty_three_weeks() -> None:
    for year in YEARS:
        assert clock.weeks_in_year(year) in (52, 53)


def test_a_week_label_round_trips_for_every_week_of_a_decade() -> None:
    for year in range(2020, 2031):
        for number in range(1, clock.weeks_in_year(year) + 1):
            label = clock.week_label(clock.week_start(year, number))
            assert clock.read_week(label) == (year, number)


def test_a_window_of_one_day_is_never_more_or_less_than_a_day_of_moments() -> None:
    for day in every_day(2025, 2025):
        first, after = window.bounds(day, day)
        opened = dt.datetime.fromisoformat(first)
        closed = dt.datetime.fromisoformat(after)
        hours = (closed - opened).total_seconds() / 3600
        assert hours in (23, 24, 25)


def test_the_two_days_the_clock_changes_are_the_short_and_the_long_one() -> None:
    short_first, short_after = window.bounds(SPRING_FORWARD, SPRING_FORWARD)
    long_first, long_after = window.bounds(FALL_BACK, FALL_BACK)
    short = dt.datetime.fromisoformat(short_after) - dt.datetime.fromisoformat(short_first)
    long = dt.datetime.fromisoformat(long_after) - dt.datetime.fromisoformat(long_first)
    assert short.total_seconds() / 3600 == 23
    assert long.total_seconds() / 3600 == 25


def test_a_window_never_ends_before_it_starts() -> None:
    for day in every_day(2025, 2026):
        first, after = window.bounds(day, day)
        assert first < after


def test_consecutive_windows_meet_without_a_gap_or_an_overlap() -> None:
    days = every_day(2025, 2025)
    for one, following in pairwise(days):
        assert window.bounds(one, one)[1] == window.bounds(following, following)[0]


def test_elapsed_is_the_real_length_across_both_clock_changes() -> None:
    spring = clock.elapsed(
        clock.moment("2025-03-09 00:00"),
        clock.moment("2025-03-10 00:00"),
    )
    autumn = clock.elapsed(
        clock.moment("2025-11-02 00:00"),
        clock.moment("2025-11-03 00:00"),
    )
    assert spring == dt.timedelta(hours=23)
    assert autumn == dt.timedelta(hours=25)


def test_a_trap_out_overnight_is_one_night_on_both_of_those_days() -> None:
    for day in (SPRING_FORWARD, FALL_BACK):
        before = day - dt.timedelta(days=1)
        out = clock.moment(f"{before.isoformat()} 16:30")
        back = clock.moment(f"{day.isoformat()} 08:15")
        assert clock.nights_between(out, back) == 1.0


@pytest.mark.parametrize("method", [AVERAGE, MODIFIED, SINE])
def test_no_day_of_a_year_of_weather_gives_negative_heat(method: str) -> None:
    for offset in range(len(every_day(2025, 2025))):
        high = 40 + (offset % 55)
        low = high - (10 + offset % 25)
        assert degree_days(high, low, 50, method) >= Decimal(0)


def test_the_modified_method_never_reads_under_the_plain_one() -> None:
    for high in range(40, 100, 3):
        for low in range(20, high + 1, 3):
            plain = degree_days(high, low, 50, AVERAGE)
            modified = degree_days(high, low, 50, MODIFIED)
            assert modified >= plain


def test_the_sine_method_sits_between_the_other_two() -> None:
    for high in range(52, 100, 3):
        for low in range(20, high, 3):
            plain = degree_days(high, low, 50, AVERAGE)
            sine = degree_days(high, low, 50, SINE)
            modified = degree_days(high, low, 50, MODIFIED)
            assert plain <= sine <= modified


def test_heat_units_never_fall_as_the_day_gets_warmer() -> None:
    for method in (AVERAGE, MODIFIED, SINE):
        found = [degree_days(high, 55, 50, method) for high in range(55, 100)]
        assert found == sorted(found)
