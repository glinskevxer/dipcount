"""What the weather record means for the round.

Two questions come out of the same readings. How far along is the brood, which
is heat, and what has just been put in the water, which is rain. They are kept
apart here because they move on different clocks and they put different sites
on the round.

An accumulation always reports its gaps. A window with three missing days is
not a window with three cold days in it, and the difference compounds: every
total for the rest of the season is short by whatever those days held. So the
gaps travel with the figure rather than being checked for separately by
whoever remembers.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import habitat as hb
from dipcount import rules, species
from dipcount.errors import RuleViolation
from dipcount.model.site import Site
from dipcount.model.weather import BASE_F, MODIFIED, Observation
from dipcount.store import sites, weather
from dipcount.store.book import Book


@dataclass(frozen=True)
class Accumulation:
    """Heat units over a window, and what the window was missing."""

    station: str
    start: dt.date
    end: dt.date
    base: float
    method: str
    total: Decimal
    counted: int
    gaps: tuple[dt.date, ...] = field(default_factory=tuple)

    @property
    def complete(self) -> bool:
        """Whether every day in the window was read."""
        return not self.gaps

    @property
    def days(self) -> int:
        """How many days the window covers."""
        return (self.end - self.start).days + 1

    def line(self) -> str:
        """One line for a report."""
        tail = "" if self.complete else f", {len(self.gaps)} missing"
        return (
            f"{self.station}  {self.start} to {self.end}"
            f"  {self.total} units base {self.base:g} by {self.method}{tail}"
        )


def accumulate(
    book: Book,
    station_id: str,
    start: dt.date,
    end: dt.date,
    *,
    base: float = float(BASE_F),
    method: str = MODIFIED,
    strict: bool = False,
) -> Accumulation:
    """Add up the heat units a station recorded over a window."""
    if end < start:
        raise RuleViolation("weather.method", "the window ends before it starts")
    station = weather.resolve_station(book, station_id)
    readings = weather.series(book, station.id, start, end)
    gaps = tuple(weather.missing_days(book, station.id, start, end))
    if strict and gaps:
        raise RuleViolation(
            "weather.gap",
            f"{station.name} is missing {len(gaps)} day(s) in this window",
        )
    total = sum((one.degree_days(base, method) for one in readings), Decimal(0))
    return Accumulation(
        station=station.id,
        start=start,
        end=end,
        base=base,
        method=method,
        total=total,
        counted=len(readings),
        gaps=gaps,
    )


def crossing(
    book: Book,
    station_id: str,
    start: dt.date,
    units: Decimal,
    *,
    base: float = float(BASE_F),
    method: str = MODIFIED,
    limit: int = 120,
) -> dt.date | None:
    """The day a running total from ``start`` first reaches ``units``."""
    station = weather.resolve_station(book, station_id)
    running = Decimal(0)
    for reading in weather.series(book, station.id, start, start + dt.timedelta(days=limit)):
        running += reading.degree_days(base, method)
        if running >= units:
            return reading.on
    return None


def emergence(
    book: Book,
    station_id: str,
    guild: str,
    laid_on: dt.date,
    *,
    base: float = float(BASE_F),
    method: str = MODIFIED,
) -> dt.date | None:
    """When a brood laid on a day should be flying, if the heat allows."""
    return crossing(
        book,
        station_id,
        laid_on,
        rules.development(guild),
        base=base,
        method=method,
    )


def wet_days(
    book: Book,
    station_id: str,
    start: dt.date,
    end: dt.date,
    *,
    at_least: Decimal = rules.FLOOD_INCHES,
) -> list[Observation]:
    """Every day at a station that put enough rain down to matter."""
    station = weather.resolve_station(book, station_id)
    return [
        one
        for one in weather.series(book, station.id, start, end)
        if Decimal(str(one.rain_in)) >= at_least
    ]


def flooded(book: Book, on: dt.date, *, within: int = rules.FLOOD_INTERVAL) -> list[Site]:
    """Every floodwater site whose zone has had a triggering rain.

    The rain is read from the stations in the site's own zone, because half an
    inch on the levee says nothing about the river bottom twenty miles away.
    """
    start = on - dt.timedelta(days=within)
    wet_zones: set[str] = set()
    for station in weather.all_stations(book):
        if wet_days(book, station.id, start, on):
            wet_zones.add(station.zone)
    out = [
        site
        for site in sites.open_on(book, on)
        if site.zone in wet_zones and species.FLOODWATER in site.kind.guilds
    ]
    return sorted(out, key=lambda site: site.id)


def rainfall(book: Book, station_id: str, start: dt.date, end: dt.date) -> Decimal:
    """How much rain a station recorded over a window."""
    station = weather.resolve_station(book, station_id)
    readings = weather.series(book, station.id, start, end)
    return sum((Decimal(str(one.rain_in)) for one in readings), Decimal(0))


def guild_forecast(
    book: Book,
    station_id: str,
    laid_on: dt.date,
    *,
    base: float = float(BASE_F),
    method: str = MODIFIED,
) -> dict[str, dt.date | None]:
    """When each guild laid on one day would be flying."""
    return {
        guild: emergence(book, station_id, guild, laid_on, base=base, method=method)
        for guild in rules.guilds()
    }


def habitats_at_risk(guild: str) -> list[str]:
    """Which habitats a guild's brood would be coming out of."""
    return [one.key for one in hb.known() if guild in one.guilds]
