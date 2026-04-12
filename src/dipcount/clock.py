"""Dates, moments and the week the surveillance year is counted in.

Arbovirus surveillance is reported by epidemiological week, not by calendar
month, so the week is a first class thing here rather than something a report
works out on its way to the printer. Week one of a year is the first week with
at least four days in January, and every week runs Sunday to Saturday. That
puts the boundary in an odd place twice a decade and there is no way around
it: the state counts the year that way, and a district that counts it any
other way cannot be added up with its neighbours.

Two smaller rules live here as well. Everything stored is UTC, so a moment
handed to the store is converted on the way in and back on the way out. And
subtracting two aware datetimes that carry the same ``zoneinfo`` does not
apply the offset, so :func:`elapsed` converts both sides to UTC first.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from dipcount.errors import UsageError

DEFAULT_ZONE = "America/Chicago"
"""Where the district is. Every naive text moment is read as this zone."""

_DAY = "%Y-%m-%d"
_MOMENT_FORMS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")


def zone(name: str = DEFAULT_ZONE) -> ZoneInfo:
    """The time zone by name, refusing an unknown one with our own error."""
    try:
        return ZoneInfo(name)
    # zoneinfo raises three different things for one spelling mistake
    except Exception as exc:
        raise UsageError(f"unknown time zone {name}") from exc


def now(name: str = DEFAULT_ZONE) -> dt.datetime:
    """The current moment in the district's zone."""
    return dt.datetime.now(tz=zone(name))


def day(text: str) -> dt.date:
    """Read a plain ``YYYY-MM-DD`` date."""
    try:
        return dt.datetime.strptime(text, _DAY).replace(tzinfo=dt.UTC).date()
    except ValueError as exc:
        raise UsageError(f"{text} is not a date in YYYY-MM-DD form") from exc


def moment(text: str, name: str = DEFAULT_ZONE) -> dt.datetime:
    """Read a local wall clock moment and attach the district's zone."""
    for form in _MOMENT_FORMS:
        try:
            naive = dt.datetime.strptime(text, form)  # noqa: DTZ007
        except ValueError:
            continue
        return naive.replace(tzinfo=zone(name))
    raise UsageError(f"{text} is not a moment in YYYY-MM-DD HH:MM form")


def to_utc(when: dt.datetime) -> dt.datetime:
    """The same moment expressed in UTC, refusing a naive datetime."""
    if when.tzinfo is None:
        raise UsageError("a moment without a zone cannot be stored")
    return when.astimezone(dt.UTC)


def in_zone(when: dt.datetime, name: str = DEFAULT_ZONE) -> dt.datetime:
    """The same moment expressed in the district's zone."""
    if when.tzinfo is None:
        raise UsageError("a moment without a zone cannot be moved")
    return when.astimezone(zone(name))


def elapsed(start: dt.datetime, end: dt.datetime) -> dt.timedelta:
    """How long ``start`` to ``end`` really is.

    Both sides go to UTC first. Subtracting two datetimes that share a
    ``ZoneInfo`` object uses wall clock arithmetic and ignores the offset, so
    an interval spanning a clock change comes out an hour wrong without this.
    """
    return to_utc(end) - to_utc(start)


def stamp(when: dt.datetime, name: str = DEFAULT_ZONE) -> str:
    """A moment printed in the district's zone, to the minute."""
    return in_zone(when, name).strftime("%Y-%m-%d %H:%M")


def week_one_end(year: int) -> dt.date:
    """The Saturday that closes week one of ``year``.

    Week one is the first week holding four or more days of January, which is
    the same as saying it ends on the first Saturday falling on or after the
    fourth.
    """
    fourth = dt.date(year, 1, 4)
    return fourth + dt.timedelta(days=(5 - fourth.weekday()) % 7)


def epi_week(when: dt.date) -> tuple[int, int]:
    """The reporting year and week number a date falls in."""
    for year in (when.year + 1, when.year, when.year - 1):
        start = week_one_end(year) - dt.timedelta(days=6)
        if when >= start:
            return year, (when - start).days // 7 + 1
    raise UsageError(f"{when.isoformat()} falls outside the week table")


def week_start(year: int, week: int) -> dt.date:
    """The Sunday that opens a given reporting week."""
    if week < 1 or week > weeks_in_year(year):
        raise UsageError(f"week {week} does not exist in {year}")
    return week_one_end(year) - dt.timedelta(days=6) + dt.timedelta(days=7 * (week - 1))


def week_end(year: int, week: int) -> dt.date:
    """The Saturday that closes a given reporting week."""
    return week_start(year, week) + dt.timedelta(days=6)


def weeks_in_year(year: int) -> int:
    """How many reporting weeks the year holds, which is 52 or 53."""
    start = week_one_end(year) - dt.timedelta(days=6)
    following = week_one_end(year + 1) - dt.timedelta(days=6)
    return (following - start).days // 7


def week_label(when: dt.date) -> str:
    """The week a date falls in, printed as ``2025-W23``."""
    year, week = epi_week(when)
    return f"{year}-W{week:02d}"


def read_week(text: str) -> tuple[int, int]:
    """Read a ``2025-W23`` label back into a year and a week."""
    head, _, tail = text.partition("-W")
    if not tail or not head.isdigit() or not tail.isdigit():
        raise UsageError(f"{text} is not a week label in YYYY-Www form")
    year, week = int(head), int(tail)
    if week < 1 or week > weeks_in_year(year):
        raise UsageError(f"week {week} does not exist in {year}")
    return year, week


def walk_weeks(first: tuple[int, int], last: tuple[int, int]) -> list[tuple[int, int]]:
    """Every reporting week from ``first`` to ``last`` inclusive."""
    start, end = week_start(*first), week_start(*last)
    if end < start:
        raise UsageError("the last week is before the first")
    out: list[tuple[int, int]] = []
    at = start
    while at <= end:
        out.append(epi_week(at))
        at += dt.timedelta(days=7)
    return out


def nights_between(set_at: dt.datetime, pulled_at: dt.datetime) -> float:
    """Trap nights between setting a trap and pulling it.

    A night is a whole twenty four hours. Traps go out in the afternoon and
    come in the next morning, which is one night and not the sixteen hours the
    clock says, so the figure is rounded to the nearest quarter and floored at
    one.
    """
    hours = elapsed(set_at, pulled_at).total_seconds() / 3600
    if hours <= 0:
        raise UsageError("a trap cannot be pulled before it was set")
    nights = round(hours / 24 * 4) / 4
    return max(nights, 1.0)
