"""Lots on the shelf, and every draw made off them.

A lot is a batch as it arrived: one product, one manufacturer code, one
delivery. Everything applied comes out of a lot, and the reason it has to be
recorded that way is a recall. When a maker pulls a code the district has to
be able to say which treatments used it and which sites they went on, and no
amount of totals by product will answer that.

Stock is not stored. It is what came in less what has gone out, worked out
from the draws every time it is asked for. A stored figure and a list of draws
that disagree is a worse position than either on its own, and they do
disagree, because a correction gets typed into one of them.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from dipcount import clock, ids
from dipcount.errors import UsageError
from dipcount.store.book import Row
from dipcount.units import Quantity

APPLIED: Final = "applied"
DISPOSED: Final = "disposed"
RETURNED: Final = "returned"
CORRECTION: Final = "correction"
REASONS: Final = (APPLIED, DISPOSED, RETURNED, CORRECTION)


@dataclass(frozen=True)
class Draw:
    """One amount taken off a lot, and what it was for."""

    seq: int
    lot: str
    at: dt.datetime
    amount: Quantity
    reason: str
    actor: str
    reference: str = ""

    def __post_init__(self) -> None:
        ids.require("lot", self.lot)
        if self.reason not in REASONS:
            raise UsageError(f"{self.reason} is not a reason: try {', '.join(REASONS)}")
        if not self.actor.strip():
            raise UsageError("a draw needs somebody's name against it")
        if self.at.tzinfo is None:
            raise UsageError("a draw needs a moment with a zone")
        if self.amount.amount == 0:
            raise UsageError("a draw of nothing is not a draw")
        if self.amount.amount < 0 and self.reason != CORRECTION:
            raise UsageError("only a correction puts product back on the shelf")

    @property
    def on(self) -> dt.date:
        """The local day this draw was made."""
        return clock.in_zone(self.at).date()

    @classmethod
    def from_row(cls, row: Row) -> Draw:
        """Read a draw off a database row."""
        return cls(
            seq=int(row["seq"]),
            lot=str(row["lot"]),
            at=dt.datetime.fromisoformat(str(row["at"])),
            amount=Quantity.parse(str(row["amount"])),
            reason=str(row["reason"]),
            actor=str(row["actor"]),
            reference=str(row["reference"]),
        )


@dataclass(frozen=True)
class Lot:
    """One batch of one product as it arrived."""

    id: str
    product: str
    code: str
    received_on: dt.date
    quantity: Quantity
    expires_on: dt.date | None = None
    held_at: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("lot", self.id)
        ids.require("product", self.product)
        if not self.code.strip():
            raise UsageError("a lot needs the code off the container")
        if self.quantity.amount <= 0:
            raise UsageError("a lot of nothing is not a lot")
        if self.expires_on is not None and self.expires_on < self.received_on:
            raise UsageError("a lot cannot expire before it arrived")

    def expired(self, on: dt.date) -> bool:
        """Whether the lot is past its date on a given day."""
        return self.expires_on is not None and on > self.expires_on

    def expires_within(self, on: dt.date, days: int) -> bool:
        """Whether the lot goes out of date inside a window."""
        if self.expires_on is None:
            return False
        return on <= self.expires_on <= on + dt.timedelta(days=days)

    @classmethod
    def from_row(cls, row: Row) -> Lot:
        """Read a lot off a database row."""
        expires = row["expires_on"]
        return cls(
            id=str(row["id"]),
            product=str(row["product"]),
            code=str(row["code"]),
            received_on=dt.date.fromisoformat(str(row["received_on"])),
            quantity=Quantity.parse(str(row["quantity"])),
            expires_on=None if expires is None else dt.date.fromisoformat(str(expires)),
            held_at=str(row["held_at"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this lot would be written as."""
        return {
            "id": self.id,
            "product": self.product,
            "code": self.code,
            "received_on": self.received_on.isoformat(),
            "quantity": str(self.quantity),
            "expires_on": None if self.expires_on is None else self.expires_on.isoformat(),
            "held_at": self.held_at,
            "note": self.note,
        }


@dataclass(frozen=True)
class Stock:
    """What is left of a lot, worked out from its draws."""

    lot: Lot
    drawn: Quantity
    draws: int = 0

    @property
    def left(self) -> Quantity:
        """What remains on the shelf."""
        return self.lot.quantity - self.drawn

    @property
    def empty(self) -> bool:
        """Whether there is nothing left."""
        return self.left.amount <= 0

    def can_take(self, amount: Quantity) -> bool:
        """Whether a draw of this size would leave the shelf standing."""
        return amount <= self.left

    def line(self) -> str:
        """One line for a stock sheet."""
        return (
            f"{self.lot.id}  {self.lot.code}  {self.left} left"
            f" of {self.lot.quantity}  {self.draws} draws"
        )
