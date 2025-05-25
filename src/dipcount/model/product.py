"""The product shelf, and what each label allows.

A pesticide label is federal law. It says what the product may be put into,
how much of it, how often, and how much of the active ingredient one acre may
receive in a season. None of those are the district's to choose, so they live
against the product rather than being typed in at the point of application.

The rate is a range and not a figure. Labels read "two point five to ten
pounds per acre" and which end of it a treatment uses is a judgement about the
water: organic load, depth, how much vegetation the granules have to get
through. Anything outside the range is not a judgement, it is an offence, so
:meth:`Label.covers` is the check every application goes through.

One more thing that surprises people. The rate is written in product, and the
seasonal cap is written in active ingredient. A product that is four percent
active and one that is thirty seven percent active can carry the same per acre
rate and reach the cap at very different points in the season.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from dipcount import habitat as hb
from dipcount import ids
from dipcount.errors import UsageError
from dipcount.store.book import Row
from dipcount.units import Quantity, Rate

LARVICIDE: Final = "larvicide"
PUPICIDE: Final = "pupicide"
ADULTICIDE: Final = "adulticide"
PURPOSES: Final = (LARVICIDE, PUPICIDE, ADULTICIDE)

CAUTION: Final = "caution"
WARNING: Final = "warning"
DANGER: Final = "danger"
SIGNALS: Final = (CAUTION, WARNING, DANGER)


@dataclass(frozen=True)
class Label:
    """What one product's label allows in one kind of water."""

    habitat: str
    low: Rate
    high: Rate
    season_max: Quantity | None = None
    interval_days: int = 0

    def __post_init__(self) -> None:
        kind = hb.habitat(self.habitat)
        if self.low.per != self.high.per:
            raise UsageError("both ends of a rate range are written against the same unit")
        if self.low.per != kind.extent_unit:
            raise UsageError(
                f"a {kind.name} is measured in {kind.extent_unit}"
                f" and this rate is per {self.low.per}",
            )
        if self.low.amount.unit != self.high.amount.unit:
            raise UsageError("both ends of a rate range are written in the same unit")
        if self.high.amount < self.low.amount:
            raise UsageError("the top of a rate range is below the bottom")
        if self.interval_days < 0:
            raise UsageError("an interval cannot be negative")

    @property
    def per(self) -> str:
        """What the rate is written against."""
        return self.low.per

    def covers(self, rate: Rate) -> bool:
        """Whether a rate is inside what the label allows."""
        if rate.per != self.per:
            return False
        moved = rate.amount.to(self.low.amount.unit)
        return self.low.amount <= moved <= self.high.amount

    def middle(self) -> Rate:
        """The middle of the range, which is where a plan starts."""
        amount = (self.low.amount + self.high.amount) / 2
        return Rate(amount, self.per)

    def line(self) -> str:
        """One line for a label sheet."""
        tail = f", no more than {self.season_max} a season" if self.season_max else ""
        gap = f", {self.interval_days} days apart" if self.interval_days else ""
        return f"{self.habitat}: {self.low.amount} to {self.high.amount} per {self.per}{tail}{gap}"

    @classmethod
    def from_row(cls, row: Row) -> Label:
        """Read a label line off a database row."""
        cap = row["season_max"]
        return cls(
            habitat=str(row["habitat"]),
            low=Rate(Quantity.parse(str(row["low_rate"])), str(row["per"])),
            high=Rate(Quantity.parse(str(row["high_rate"])), str(row["per"])),
            season_max=None if cap is None else Quantity.parse(str(cap)),
            interval_days=int(row["interval_days"]),
        )


@dataclass(frozen=True)
class Product:
    """One thing on the shelf, with its registration and its label."""

    id: str
    name: str
    registration: str
    maker: str
    active: str
    percent: Decimal
    form: str
    purpose: str
    added_on: dt.date
    restricted: bool = False
    signal: str = CAUTION
    reentry: int = 0
    withdrawn_on: dt.date | None = None
    note: str = ""
    labels: tuple[Label, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ids.require("product", self.id)
        if not self.name.strip():
            raise UsageError("a product needs a name")
        if not self.registration.strip():
            raise UsageError("a product needs a registration number")
        if self.purpose not in PURPOSES:
            raise UsageError(f"{self.purpose} is not a purpose: try {', '.join(PURPOSES)}")
        if self.signal not in SIGNALS:
            raise UsageError(f"{self.signal} is not a signal word: try {', '.join(SIGNALS)}")
        if self.form not in hb.forms():
            raise UsageError(f"{self.form} is not a formulation this district handles")
        if not 0 < self.percent <= 100:
            raise UsageError(f"{self.percent} is not a share of active ingredient")
        if self.reentry < 0:
            raise UsageError("a reentry interval cannot be negative")
        if self.withdrawn_on is not None and self.withdrawn_on < self.added_on:
            raise UsageError("a product cannot be withdrawn before it was added")
        if len({one.habitat for one in self.labels}) != len(self.labels):
            raise UsageError("a label cannot carry two entries for one habitat")

    def on_shelf(self, on: dt.date) -> bool:
        """Whether the product was in use on a day."""
        if on < self.added_on:
            return False
        return self.withdrawn_on is None or on <= self.withdrawn_on

    def label_for(self, habitat: str) -> Label | None:
        """What the label says about one kind of water, if anything."""
        for one in self.labels:
            if one.habitat == habitat:
                return one
        return None

    def labelled_habitats(self) -> list[str]:
        """Every kind of water this product may go into."""
        return sorted(one.habitat for one in self.labels)

    def active_in(self, amount: Quantity) -> Quantity:
        """How much active ingredient an amount of product holds."""
        return amount * (self.percent / Decimal(100))

    @classmethod
    def from_row(cls, row: Row, labels: tuple[Label, ...] = ()) -> Product:
        """Read a product off a database row and its label rows."""
        withdrawn = row["withdrawn_on"]
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            registration=str(row["registration"]),
            maker=str(row["maker"]),
            active=str(row["active"]),
            percent=Decimal(str(row["percent"])),
            form=str(row["form"]),
            purpose=str(row["purpose"]),
            added_on=dt.date.fromisoformat(str(row["added_on"])),
            restricted=bool(row["restricted"]),
            signal=str(row["signal"]),
            reentry=int(row["reentry"]),
            withdrawn_on=None if withdrawn is None else dt.date.fromisoformat(str(withdrawn)),
            note=str(row["note"]),
            labels=labels,
        )

    def to_row(self) -> dict[str, object]:
        """The row this product would be written as."""
        return {
            "id": self.id,
            "name": self.name,
            "registration": self.registration,
            "maker": self.maker,
            "active": self.active,
            "percent": float(self.percent),
            "form": self.form,
            "purpose": self.purpose,
            "restricted": int(self.restricted),
            "signal": self.signal,
            "reentry": self.reentry,
            "added_on": self.added_on.isoformat(),
            "withdrawn_on": None if self.withdrawn_on is None else self.withdrawn_on.isoformat(),
            "note": self.note,
        }
