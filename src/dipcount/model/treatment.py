"""A treatment: product, place, amount, day and the person who made it.

This is the record the state asks for and the record a lawsuit would ask for,
so it holds everything needed to reconstruct the application without looking
anything else up: which lot, over how much ground, how much went on, and who
put it there.

The rate is not stored. It is the amount over the extent, and storing it as
well as both of those is storing the same fact twice in a form that can
disagree with itself. Every report that wants a rate works it out.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from dipcount import clock, ids
from dipcount.errors import UsageError
from dipcount.store.book import Row
from dipcount.units import Quantity, Rate


@dataclass(frozen=True)
class Treatment:
    """One application of one product at one site."""

    id: str
    site: str
    product: str
    lot: str
    at: dt.datetime
    applicator: str
    extent: Quantity
    amount: Quantity
    equipment: str = ""
    inspection: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("treatment", self.id)
        ids.require("site", self.site)
        ids.require("product", self.product)
        ids.require("lot", self.lot)
        if self.inspection is not None:
            ids.require("inspection", self.inspection)
        if not self.applicator.strip():
            raise UsageError("a treatment needs the name of whoever made it")
        if self.at.tzinfo is None:
            raise UsageError("a treatment needs a moment with a zone")
        if self.extent.amount <= 0:
            raise UsageError("a treatment over nothing is not a treatment")
        if self.amount.amount <= 0:
            raise UsageError("a treatment of nothing is not a treatment")
        if ids.day_of(self.id) != clock.in_zone(self.at).date():
            raise UsageError(f"{self.id} does not carry the day it was made on")

    @property
    def on(self) -> dt.date:
        """The local day the treatment was made."""
        return clock.in_zone(self.at).date()

    @property
    def week(self) -> str:
        """The reporting week the treatment falls in."""
        return clock.week_label(self.on)

    @property
    def rate(self) -> Rate:
        """What went on, per unit of what it went on."""
        return Rate(self.amount / self.extent.amount, self.extent.unit)

    def active(self, percent: Decimal) -> Quantity:
        """How much active ingredient this treatment put down."""
        return self.amount * (percent / Decimal(100))

    def line(self) -> str:
        """One line for a use report."""
        return (
            f"{self.on.isoformat()}  {self.id}  {self.site}"
            f"  {self.amount} over {self.extent}  {self.rate}  {self.applicator}"
        )

    @classmethod
    def from_row(cls, row: Row) -> Treatment:
        """Read a treatment off a database row."""
        inspection = row["inspection"]
        return cls(
            id=str(row["id"]),
            site=str(row["site"]),
            product=str(row["product"]),
            lot=str(row["lot"]),
            at=dt.datetime.fromisoformat(str(row["at"])),
            applicator=str(row["applicator"]),
            extent=Quantity.parse(str(row["extent"])),
            amount=Quantity.parse(str(row["amount"])),
            equipment=str(row["equipment"]),
            inspection=None if inspection is None else str(inspection),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this treatment would be written as."""
        return {
            "id": self.id,
            "site": self.site,
            "product": self.product,
            "lot": self.lot,
            "at": clock.to_utc(self.at).isoformat(),
            "applicator": self.applicator,
            "extent": str(self.extent),
            "amount": str(self.amount),
            "equipment": self.equipment,
            "inspection": self.inspection,
            "note": self.note,
        }
