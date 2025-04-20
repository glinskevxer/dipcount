"""Traps, the collections that come off them, and what is in the jar.

A trap is not a site. A site is water the district can treat; a trap is a
point where adults are caught to find out what is flying and what it is
carrying. They are counted differently, they are visited on different rounds,
and a trap sits on somebody's fence post rather than over anything.

The index every report is written in is females per trap night. Both halves of
that are easy to get wrong. Males are caught, recorded, and then left out of
the index, because a male mosquito does not bite anything and does not carry
anything. And a trap that was found knocked over, or whose battery was flat,
produced no data rather than a night of zero, so ``worked`` and a catch of
nothing are not the same record.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from dipcount import clock, ids, species
from dipcount.errors import UsageError
from dipcount.store.book import Row

FEMALE: Final = "F"
MALE: Final = "M"
SEXES: Final = (FEMALE, MALE)


@dataclass(frozen=True)
class TrapKind:
    """One kind of trap, and what it is good for."""

    key: str
    name: str
    guilds: tuple[str, ...]
    lure: str
    catches_gravid: bool = False
    note: str = ""


KINDS: Final[dict[str, TrapKind]] = {
    kind.key: kind
    for kind in (
        TrapKind(
            "light",
            "CDC light trap with dry ice",
            (species.FLOODWATER, species.PERMANENT, species.WOODLAND),
            "carbon dioxide",
            note="host seeking females, and the broadest picture of what is flying",
        ),
        TrapKind(
            "gravid",
            "gravid trap over hay infusion",
            (species.PERMANENT,),
            "hay infusion",
            catches_gravid=True,
            note="females that have already fed, which is where the virus is",
        ),
        TrapKind(
            "bg",
            "BG Sentinel",
            (species.CONTAINER,),
            "lure and carbon dioxide",
            note="the container species, which the light trap hardly sees",
        ),
        TrapKind(
            "resting",
            "resting box",
            (species.PERMANENT, species.WOODLAND),
            "shelter",
            catches_gravid=True,
            note="unbaited, so it catches what is nearby rather than what comes",
        ),
    )
}


def trap_kind(key: str) -> TrapKind:
    """One kind of trap by key."""
    try:
        return KINDS[key]
    except KeyError as exc:
        raise UsageError(f"{key} is not a kind of trap: try {', '.join(KINDS)}") from exc


@dataclass(frozen=True)
class Trap:
    """One trap station the district runs."""

    id: str
    zone: str
    name: str
    kind: str
    listed_on: dt.date
    latitude: float | None = None
    longitude: float | None = None
    retired_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("trap", self.id)
        ids.require("zone", self.zone)
        if not self.name.strip():
            raise UsageError("a trap needs a name")
        trap_kind(self.kind)
        if self.retired_on is not None and self.retired_on < self.listed_on:
            raise UsageError("a trap cannot be retired before it was listed")

    @property
    def sort(self) -> TrapKind:
        """What kind of trap this is."""
        return trap_kind(self.kind)

    def is_open(self, on: dt.date) -> bool:
        """Whether the trap was running on a given day."""
        if on < self.listed_on:
            return False
        return self.retired_on is None or on <= self.retired_on

    @classmethod
    def from_row(cls, row: Row) -> Trap:
        """Read a trap off a database row."""
        retired = row["retired_on"]
        return cls(
            id=str(row["id"]),
            zone=str(row["zone"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            listed_on=dt.date.fromisoformat(str(row["listed_on"])),
            latitude=None if row["latitude"] is None else float(row["latitude"]),
            longitude=None if row["longitude"] is None else float(row["longitude"]),
            retired_on=None if retired is None else dt.date.fromisoformat(str(retired)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this trap would be written as."""
        return {
            "id": self.id,
            "zone": self.zone,
            "name": self.name,
            "kind": self.kind,
            "listed_on": self.listed_on.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "retired_on": None if self.retired_on is None else self.retired_on.isoformat(),
            "note": self.note,
        }


@dataclass(frozen=True)
class Catch:
    """How many of one species and sex were in the jar."""

    species: str
    sex: str
    tally: int

    def __post_init__(self) -> None:
        if self.sex not in SEXES:
            raise UsageError(f"{self.sex} is not a sex: try {' or '.join(SEXES)}")
        if self.tally < 0:
            raise UsageError("a catch cannot be negative")
        species.species(self.species)

    @property
    def counts(self) -> bool:
        """Whether this line belongs in the index."""
        return self.sex == FEMALE

    @classmethod
    def from_row(cls, row: Row) -> Catch:
        """Read a catch off a database row."""
        return cls(str(row["species"]), str(row["sex"]), int(row["tally"]))


@dataclass(frozen=True)
class Collection:
    """One trap, set on one evening and pulled on another morning."""

    id: str
    trap: str
    set_at: dt.datetime
    pulled_at: dt.datetime
    handler: str
    worked: bool = True
    note: str = ""
    catches: tuple[Catch, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ids.require("collection", self.id)
        ids.require("trap", self.trap)
        if not self.handler.strip():
            raise UsageError("a collection needs the name of whoever pulled it")
        if self.set_at.tzinfo is None or self.pulled_at.tzinfo is None:
            raise UsageError("a collection needs moments with zones")
        if not self.worked and self.catches:
            raise UsageError("a trap that did not run cannot have caught anything")

    @property
    def nights(self) -> Decimal:
        """How many trap nights this collection represents."""
        return Decimal(str(clock.nights_between(self.set_at, self.pulled_at)))

    @property
    def on(self) -> dt.date:
        """The local day the trap was pulled, which is the collection date."""
        return clock.in_zone(self.pulled_at).date()

    @property
    def week(self) -> str:
        """The reporting week the collection falls in."""
        return clock.week_label(self.on)

    @property
    def females(self) -> int:
        """Every female in the jar, of any species."""
        return sum(one.tally for one in self.catches if one.counts)

    @property
    def males(self) -> int:
        """Every male in the jar, which is recorded and not indexed."""
        return sum(one.tally for one in self.catches if not one.counts)

    @property
    def total(self) -> int:
        """Everything in the jar."""
        return self.females + self.males

    @property
    def index(self) -> Decimal:
        """Females per trap night, which is what the reports are written in."""
        if not self.worked:
            return Decimal(0)
        return Decimal(self.females) / self.nights

    def females_of(self, code: str) -> int:
        """Females of one species."""
        return sum(one.tally for one in self.catches if one.counts and one.species == code)

    def index_of(self, code: str) -> Decimal:
        """Females per trap night for one species."""
        if not self.worked:
            return Decimal(0)
        return Decimal(self.females_of(code)) / self.nights

    def species_seen(self) -> list[str]:
        """Every species in the jar, in code order."""
        return sorted({one.species for one in self.catches})

    @classmethod
    def from_row(cls, row: Row, catches: tuple[Catch, ...] = ()) -> Collection:
        """Read a collection off a database row and its catch rows."""
        return cls(
            id=str(row["id"]),
            trap=str(row["trap"]),
            set_at=dt.datetime.fromisoformat(str(row["set_at"])),
            pulled_at=dt.datetime.fromisoformat(str(row["pulled_at"])),
            handler=str(row["handler"]),
            worked=bool(row["worked"]),
            note=str(row["note"]),
            catches=catches,
        )

    def to_row(self) -> dict[str, object]:
        """The row this collection would be written as."""
        return {
            "id": self.id,
            "trap": self.trap,
            "set_at": clock.to_utc(self.set_at).isoformat(),
            "pulled_at": clock.to_utc(self.pulled_at).isoformat(),
            "nights": float(self.nights),
            "worked": int(self.worked),
            "handler": self.handler,
            "note": self.note,
        }
