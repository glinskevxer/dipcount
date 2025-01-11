from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock
from dipcount.errors import UsageError


def test_week_one_ends_on_the_first_saturday_from_the_fourth() -> None:
    assert clock.week_one_end(2025) == dt.date(2025, 1, 4)
    assert clock.week_one_end(2026) == dt.date(2026, 1, 10)
    assert clock.week_one_end(2024) == dt.date(2024, 1, 6)


def test_every_week_one_end_is_a_saturday() -> None:
    for year in range(2015, 2041):
        assert clock.week_one_end(year).weekday() == 5


def test_week_one_holds_four_days_of_january() -> None:
    for year in range(2015, 2041):
        end = clock.week_one_end(year)
        days = [end - dt.timedelta(days=n) for n in range(7)]
        assert sum(1 for d in days if d.month == 1 and d.year == year) >= 4


def test_the_year_rolls_over_inside_a_week() -> None:
    assert clock.epi_week(dt.date(2025, 12, 28)) == (2025, 53)
    assert clock.epi_week(dt.date(2026, 1, 3)) == (2025, 53)
    assert clock.epi_week(dt.date(2026, 1, 4)) == (2026, 1)


def test_2025_is_a_fifty_three_week_year() -> None:
    assert clock.weeks_in_year(2025) == 53
    assert clock.weeks_in_year(2026) == 52


def test_week_start_and_end_bracket_the_week() -> None:
    start = clock.week_start(2025, 23)
    end = clock.week_end(2025, 23)
    assert start.weekday() == 6
    assert end.weekday() == 5
    assert (end - start).days == 6
    assert clock.epi_week(start) == (2025, 23)
    assert clock.epi_week(end) == (2025, 23)


def test_every_day_of_a_year_lands_in_exactly_one_week() -> None:
    at = dt.date(2025, 1, 1)
    seen: dict[dt.date, tuple[int, int]] = {}
    while at < dt.date(2027, 1, 1):
        year, week = clock.epi_week(at)
        assert clock.week_start(year, week) <= at <= clock.week_end(year, week)
        seen[at] = (year, week)
        at += dt.timedelta(days=1)
    assert len(seen) == 730


def test_a_week_outside_the_year_is_refused() -> None:
    with pytest.raises(UsageError):
        clock.week_start(2026, 53)
    with pytest.raises(UsageError):
        clock.week_start(2025, 0)


def test_week_label_round_trips() -> None:
    assert clock.week_label(dt.date(2025, 6, 4)) == "2025-W23"
    assert clock.read_week("2025-W23") == (2025, 23)


def test_a_bad_week_label_is_refused() -> None:
    for text in ("2025", "week 23", "2025-Wxx", "2026-W53"):
        with pytest.raises(UsageError):
            clock.read_week(text)


def test_walking_weeks_crosses_the_year() -> None:
    weeks = clock.walk_weeks((2025, 52), (2026, 2))
    assert weeks == [(2025, 52), (2025, 53), (2026, 1), (2026, 2)]


def test_walking_backwards_is_refused() -> None:
    with pytest.raises(UsageError):
        clock.walk_weeks((2025, 20), (2025, 10))


def test_elapsed_applies_the_offset_over_a_clock_change() -> None:
    tz = clock.zone()
    start = dt.datetime(2025, 3, 9, 1, 0, tzinfo=tz)
    end = dt.datetime(2025, 3, 9, 4, 0, tzinfo=tz)
    assert clock.elapsed(start, end) == dt.timedelta(hours=2)
    assert end - start == dt.timedelta(hours=3)


def test_a_naive_moment_cannot_be_stored() -> None:
    with pytest.raises(UsageError):
        clock.to_utc(dt.datetime(2025, 6, 1, 12, 0))  # noqa: DTZ001


def test_moments_read_in_several_forms() -> None:
    forms = ["2025-06-04 21:30", "2025-06-04T21:30", "2025-06-04 21:30:00"]
    read = {clock.moment(f) for f in forms}
    assert len(read) == 1
    assert clock.stamp(read.pop()) == "2025-06-04 21:30"


def test_a_bad_moment_is_refused() -> None:
    with pytest.raises(UsageError):
        clock.moment("last tuesday")
    with pytest.raises(UsageError):
        clock.day("2025/06/04")


def test_an_unknown_zone_is_our_error() -> None:
    with pytest.raises(UsageError):
        clock.zone("Mars/Olympus")


def test_a_trap_set_overnight_is_one_night() -> None:
    out = clock.moment("2025-06-04 16:30")
    back = clock.moment("2025-06-05 08:15")
    assert clock.nights_between(out, back) == 1.0


def test_three_nights_out_counts_three() -> None:
    out = clock.moment("2025-06-04 16:00")
    back = clock.moment("2025-06-07 16:00")
    assert clock.nights_between(out, back) == 3.0


def test_a_trap_pulled_before_it_was_set_is_refused() -> None:
    out = clock.moment("2025-06-04 16:00")
    with pytest.raises(UsageError):
        clock.nights_between(out, out)


def test_now_carries_a_zone() -> None:
    assert clock.now().tzinfo is not None
    assert clock.to_utc(clock.now()).tzinfo is dt.UTC
    assert clock.in_zone(clock.now(), "UTC").utcoffset() == dt.timedelta(0)
