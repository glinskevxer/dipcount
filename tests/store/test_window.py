from __future__ import annotations

import datetime as dt

from dipcount import clock
from dipcount.store import window


def test_a_window_runs_from_midnight_to_midnight() -> None:
    first, after = window.bounds(dt.date(2025, 6, 4), dt.date(2025, 6, 6))
    assert clock.stamp(dt.datetime.fromisoformat(first)) == "2025-06-04 00:00"
    assert clock.stamp(dt.datetime.fromisoformat(after)) == "2025-06-07 00:00"


def test_both_ends_the_supervisor_named_are_inside_it() -> None:
    first, after = window.bounds(dt.date(2025, 6, 4), dt.date(2025, 6, 4))
    late = clock.to_utc(clock.moment("2025-06-04 23:59")).isoformat()
    assert first <= late < after


def test_one_day_is_a_window_of_one_day() -> None:
    assert window.day(dt.date(2025, 6, 4)) == window.bounds(
        dt.date(2025, 6, 4),
        dt.date(2025, 6, 4),
    )


def test_a_week_covers_sunday_to_the_saturday_after() -> None:
    first, after = window.week(2025, 23)
    assert clock.stamp(dt.datetime.fromisoformat(first)) == "2025-06-01 00:00"
    assert clock.stamp(dt.datetime.fromisoformat(after)) == "2025-06-08 00:00"


def test_the_bounds_are_stored_in_utc() -> None:
    first, after = window.bounds(dt.date(2025, 6, 4), dt.date(2025, 6, 4))
    assert first.endswith("+00:00")
    assert after.endswith("+00:00")


def test_the_offset_moves_with_the_season() -> None:
    summer, _ = window.bounds(dt.date(2025, 7, 4), dt.date(2025, 7, 4))
    winter, _ = window.bounds(dt.date(2025, 1, 4), dt.date(2025, 1, 4))
    assert summer[11:13] == "05"
    assert winter[11:13] == "06"


def test_another_zone_gives_another_pair() -> None:
    here, _ = window.bounds(dt.date(2025, 6, 4), dt.date(2025, 6, 4))
    away, _ = window.bounds(dt.date(2025, 6, 4), dt.date(2025, 6, 4), "UTC")
    assert here != away


def test_one_moment_is_stored_as_utc() -> None:
    assert window.from_moment(clock.moment("2025-06-04 09:00")).endswith("+00:00")
