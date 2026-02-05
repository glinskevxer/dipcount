"""Spray blocks, the notices given over them, and the runs made.

A block is the piece of ground a truck fogs in one pass of a street grid. It
is measured in acres for the label rate and in road miles for the driving, and
the two do not move together: a block of small lots has a lot of road for its
acreage and a block of half section farmland has almost none.

Notice is written against the pairing of a place and a block, not against
either alone. A beekeeper on the edge of three blocks gets told about the one
being run, and a notice for last Tuesday's block is not a notice for this
one. The notice also carries the window it covers, because a keeper told
"some time this week" has not been told anything they can act on.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from dipcount import clock, ids
from dipcount.errors import UsageError
from dipcount.rows import Row
from dipcount.units import Quantity, Rate

PHONE: Final = "phone"
TEXT: Final = "text message"
EMAIL: Final = "email"
CARD: Final = "card through the door"
DOOR: Final = "spoken to at the door"
WAYS: Final = (PHONE, TEXT, EMAIL, CARD, DOOR)


@dataclass(frozen=True)
class Block:
    """One piece of ground a truck runs in a night."""

    id: str
    zone: str
    name: str
    acres: float
    listed_on: dt.date
    road_miles: float = 0.0
    retired_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("block", self.id)
        ids.require("zone", self.zone)
        if not self.name.strip():
            raise UsageError("a block needs a name")
        if self.acres <= 0:
            raise UsageError("a block with no acres is not a block")
        if self.road_miles < 0:
            raise UsageError("road miles cannot be negative")
        if self.retired_on is not None and self.retired_on < self.listed_on:
            raise UsageError("a block cannot be retired before it was listed")

    @property
    def extent(self) -> Quantity:
        """The block as a quantity, for a rate to be applied over."""
        return Quantity(Decimal(str(self.acres)), "acre")

    def is_open(self, on: dt.date) -> bool:
        """Whether the block was on the run list on a day."""
        if on < self.listed_on:
            return False
        return self.retired_on is None or on <= self.retired_on

    @classmethod
    def from_row(cls, row: Row) -> Block:
        """Read a block off a database row."""
        retired = row["retired_on"]
        return cls(
            id=str(row["id"]),
            zone=str(row["zone"]),
            name=str(row["name"]),
            acres=float(row["acres"]),
            listed_on=dt.date.fromisoformat(str(row["listed_on"])),
            road_miles=float(row["road_miles"]),
            retired_on=None if retired is None else dt.date.fromisoformat(str(retired)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this block would be written as."""
        return {
            "id": self.id,
            "zone": self.zone,
            "name": self.name,
            "acres": self.acres,
            "listed_on": self.listed_on.isoformat(),
            "road_miles": self.road_miles,
            "retired_on": None if self.retired_on is None else self.retired_on.isoformat(),
            "note": self.note,
        }


@dataclass(frozen=True)
class Notice:
    """One place told about one block, for one window."""

    id: str
    exclusion: str
    block: str
    given_at: dt.datetime
    spray_from: dt.datetime
    spray_to: dt.datetime
    how: str
    given_by: str
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("notice", self.id)
        ids.require("exclusion", self.exclusion)
        ids.require("block", self.block)
        if self.how not in WAYS:
            raise UsageError(f"{self.how} is not a way of telling: try {', '.join(WAYS)}")
        if not self.given_by.strip():
            raise UsageError("a notice needs the name of whoever gave it")
        for moment in (self.given_at, self.spray_from, self.spray_to):
            if moment.tzinfo is None:
                raise UsageError("a notice needs moments with zones")
        if self.spray_to <= self.spray_from:
            raise UsageError("a notice window ends before it starts")
        if self.given_at > self.spray_from:
            raise UsageError("a notice given after the window opens is not notice")

    @property
    def hours_given(self) -> Decimal:
        """How much warning this notice actually gave."""
        seconds = clock.elapsed(self.given_at, self.spray_from).total_seconds()
        return Decimal(str(round(seconds / 3600, 2)))

    def covers(self, at: dt.datetime) -> bool:
        """Whether a run starting at a moment is inside this notice."""
        return self.spray_from <= at <= self.spray_to

    def line(self) -> str:
        """One line for a notice sheet."""
        return (
            f"{self.id}  {self.exclusion}  {self.block}"
            f"  told {clock.stamp(self.given_at)} by {self.how}"
            f"  window {clock.stamp(self.spray_from)} to {clock.stamp(self.spray_to)}"
        )

    @classmethod
    def from_row(cls, row: Row) -> Notice:
        """Read a notice off a database row."""
        return cls(
            id=str(row["id"]),
            exclusion=str(row["exclusion"]),
            block=str(row["block"]),
            given_at=dt.datetime.fromisoformat(str(row["given_at"])),
            spray_from=dt.datetime.fromisoformat(str(row["spray_from"])),
            spray_to=dt.datetime.fromisoformat(str(row["spray_to"])),
            how=str(row["how"]),
            given_by=str(row["given_by"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this notice would be written as."""
        return {
            "id": self.id,
            "exclusion": self.exclusion,
            "block": self.block,
            "given_at": clock.to_utc(self.given_at).isoformat(),
            "spray_from": clock.to_utc(self.spray_from).isoformat(),
            "spray_to": clock.to_utc(self.spray_to).isoformat(),
            "how": self.how,
            "given_by": self.given_by,
            "note": self.note,
        }


@dataclass(frozen=True)
class Run:
    """One night's fogging over one block."""

    id: str
    block: str
    product: str
    lot: str
    applicator: str
    started_at: dt.datetime
    finished_at: dt.datetime
    amount: Quantity
    acres: float
    licence: str = ""
    equipment: str = ""
    temperature: float | None = None
    wind_mph: float | None = None
    wind_from: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("run", self.id)
        ids.require("block", self.block)
        ids.require("product", self.product)
        ids.require("lot", self.lot)
        if not self.applicator.strip():
            raise UsageError("a run needs the name of whoever made it")
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise UsageError("a run needs moments with zones")
        if self.finished_at <= self.started_at:
            raise UsageError("a run cannot finish before it starts")
        if self.acres <= 0:
            raise UsageError("a run over nothing is not a run")
        if self.amount.amount <= 0:
            raise UsageError("a run of nothing is not a run")

    @property
    def on(self) -> dt.date:
        """The local day the run started."""
        return clock.in_zone(self.started_at).date()

    @property
    def minutes(self) -> Decimal:
        """How long the truck was spraying."""
        seconds = clock.elapsed(self.started_at, self.finished_at).total_seconds()
        return Decimal(str(round(seconds / 60, 1)))

    @property
    def rate(self) -> Rate:
        """What went on, per acre."""
        return Rate(self.amount / Decimal(str(self.acres)), "acre")

    def line(self) -> str:
        """One line for a use report."""
        return (
            f"{self.on.isoformat()}  {self.id}  {self.block}"
            f"  {self.amount} over {self.acres:g} acre  {self.rate}  {self.applicator}"
        )

    @classmethod
    def from_row(cls, row: Row) -> Run:
        """Read a run off a database row."""
        return cls(
            id=str(row["id"]),
            block=str(row["block"]),
            product=str(row["product"]),
            lot=str(row["lot"]),
            applicator=str(row["applicator"]),
            started_at=dt.datetime.fromisoformat(str(row["started_at"])),
            finished_at=dt.datetime.fromisoformat(str(row["finished_at"])),
            amount=Quantity.parse(str(row["amount"])),
            acres=float(row["acres"]),
            licence=str(row["licence"]),
            equipment=str(row["equipment"]),
            temperature=None if row["temperature"] is None else float(row["temperature"]),
            wind_mph=None if row["wind_mph"] is None else float(row["wind_mph"]),
            wind_from=str(row["wind_from"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this run would be written as."""
        return {
            "id": self.id,
            "block": self.block,
            "product": self.product,
            "lot": self.lot,
            "applicator": self.applicator,
            "licence": self.licence,
            "started_at": clock.to_utc(self.started_at).isoformat(),
            "finished_at": clock.to_utc(self.finished_at).isoformat(),
            "amount": str(self.amount),
            "acres": self.acres,
            "equipment": self.equipment,
            "temperature": self.temperature,
            "wind_mph": self.wind_mph,
            "wind_from": self.wind_from,
            "note": self.note,
        }
