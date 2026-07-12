"""Turning a run of local days into the pair of moments a query wants.

Everything is stored in UTC and everything is asked for in local days, so
every store that keeps dated records has to turn one into the other. Five of
them were doing it, and two of them were doing it slightly differently: one
took the end day as exclusive and the other as inclusive, which is a
difference of one day at the end of every window and shows up as a report that
is right in June and short in December.

The rule is that a window runs from midnight local on the first day to
midnight local on the day after the last, so both ends of the window a
supervisor names are inside it.
"""

from __future__ import annotations

import datetime as dt

from dipcount import clock


def bounds(start: dt.date, end: dt.date, zone: str = clock.DEFAULT_ZONE) -> tuple[str, str]:
    """The pair of stored moments a run of local days covers."""
    first = clock.moment(f"{start.isoformat()} 00:00", zone)
    after = clock.moment(f"{(end + dt.timedelta(days=1)).isoformat()} 00:00", zone)
    return clock.to_utc(first).isoformat(), clock.to_utc(after).isoformat()


def day(on: dt.date, zone: str = clock.DEFAULT_ZONE) -> tuple[str, str]:
    """The pair of stored moments one local day covers."""
    return bounds(on, on, zone)


def week(year: int, number: int, zone: str = clock.DEFAULT_ZONE) -> tuple[str, str]:
    """The pair of stored moments one reporting week covers."""
    return bounds(clock.week_start(year, number), clock.week_end(year, number), zone)


def from_moment(at: dt.datetime) -> str:
    """One moment as it is stored."""
    return clock.to_utc(at).isoformat()
