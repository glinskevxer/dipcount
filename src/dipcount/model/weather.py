"""Weather stations and the daily observation each one files.

The district watches the weather for two different reasons and they want two
different numbers out of it. Development runs on heat, so the larval programme
counts degree days above a base and asks how far along a brood should be. The
floodwater species run on rain, so a half inch overnight is a brood in four
days whatever the heat has been doing.

Degree days can be worked out three ways and they do not agree. The plain
average takes the mean of the day's high and low and subtracts the base, which
goes negative on a cold night and quietly cancels out a warm day. The modified
method lifts the low to the base first, so a cold night contributes nothing
rather than contributing backwards. The single sine method fits a curve
between the two and takes the area above the base, which is the one the state
publishes. Which of the three a district uses is a choice, and a season
accumulated one way cannot be compared with a season accumulated another.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal

from dipcount import ids
from dipcount.errors import UsageError
from dipcount.store.book import Row

AVERAGE = "average"
MODIFIED = "modified"
SINE = "single sine"
METHODS = (AVERAGE, MODIFIED, SINE)

BASE_F = Decimal("50")
"""The base the district accumulates against, in Fahrenheit."""


def degree_days(high: float, low: float, base: float = 50.0, method: str = MODIFIED) -> Decimal:
    """Heat units for one day, by one of the three methods."""
    if method not in METHODS:
        raise UsageError(f"{method} is not a degree day method: try {', '.join(METHODS)}")
    if low > high:
        raise UsageError("the low cannot be above the high")
    if method == AVERAGE:
        return _round((high + low) / 2 - base)
    if method == MODIFIED:
        return _round((high + max(low, base)) / 2 - base)
    return _single_sine(high, low, base)


def _round(value: float) -> Decimal:
    return Decimal(str(round(max(value, 0.0), 2)))


def _single_sine(high: float, low: float, base: float) -> Decimal:
    """The area of one sine curve above the base, over a whole day."""
    if high <= base:
        return Decimal("0")
    mean = (high + low) / 2
    amplitude = (high - low) / 2
    if low >= base:
        return _round(mean - base)
    if amplitude == 0:
        return _round(mean - base)
    theta = math.asin((base - mean) / amplitude)
    area = ((mean - base) * (math.pi / 2 - theta) + amplitude * math.cos(theta)) / math.pi
    return _round(area)


@dataclass(frozen=True)
class Station:
    """One weather station the district reads."""

    id: str
    name: str
    zone: str
    opened_on: dt.date
    elevation: int = 0
    closed_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("station", self.id)
        ids.require("zone", self.zone)
        if not self.name.strip():
            raise UsageError("a station needs a name")
        if self.closed_on is not None and self.closed_on < self.opened_on:
            raise UsageError("a station cannot close before it opened")

    def is_open(self, on: dt.date) -> bool:
        """Whether the station was reading on a given day."""
        if on < self.opened_on:
            return False
        return self.closed_on is None or on <= self.closed_on

    @classmethod
    def from_row(cls, row: Row) -> Station:
        """Read a station off a database row."""
        closed = row["closed_on"]
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            zone=str(row["zone"]),
            opened_on=dt.date.fromisoformat(str(row["opened_on"])),
            elevation=int(row["elevation"]),
            closed_on=None if closed is None else dt.date.fromisoformat(str(closed)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this station would be written as."""
        return {
            "id": self.id,
            "name": self.name,
            "zone": self.zone,
            "opened_on": self.opened_on.isoformat(),
            "elevation": self.elevation,
            "closed_on": None if self.closed_on is None else self.closed_on.isoformat(),
            "note": self.note,
        }


@dataclass(frozen=True)
class Observation:
    """What one station recorded on one day."""

    id: str
    station: str
    on: dt.date
    high_f: float
    low_f: float
    rain_in: float = 0.0
    wind_mph: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("observation", self.id)
        ids.require("station", self.station)
        if self.low_f > self.high_f:
            raise UsageError(f"a low of {self.low_f} is above a high of {self.high_f}")
        if self.rain_in < 0:
            raise UsageError("rainfall cannot be negative")
        if self.wind_mph < 0:
            raise UsageError("wind speed cannot be negative")
        if ids.day_of(self.id) != self.on:
            raise UsageError(f"{self.id} does not carry {self.on.isoformat()}")

    @property
    def mean_f(self) -> float:
        """The day's mean temperature."""
        return (self.high_f + self.low_f) / 2

    def degree_days(self, base: float = 50.0, method: str = MODIFIED) -> Decimal:
        """Heat units this day contributed."""
        return degree_days(self.high_f, self.low_f, base, method)

    @property
    def wet(self) -> bool:
        """Whether anything measurable fell."""
        return self.rain_in >= 0.01

    @classmethod
    def from_row(cls, row: Row) -> Observation:
        """Read an observation off a database row."""
        return cls(
            id=str(row["id"]),
            station=str(row["station"]),
            on=dt.date.fromisoformat(str(row["on_day"])),
            high_f=float(row["high_f"]),
            low_f=float(row["low_f"]),
            rain_in=float(row["rain_in"]),
            wind_mph=float(row["wind_mph"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this observation would be written as."""
        return {
            "id": self.id,
            "station": self.station,
            "on_day": self.on.isoformat(),
            "high_f": self.high_f,
            "low_f": self.low_f,
            "rain_in": self.rain_in,
            "wind_mph": self.wind_mph,
            "note": self.note,
        }
