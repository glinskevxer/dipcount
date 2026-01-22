"""The pesticide use report the state asks for.

One row for every application the district made, whether it went into water or
out of a fogger. The two are different records in this package and the state
does not care: what it wants is the day, the place, the product with its
registration number, how much went on, over what area, and the certification
number of whoever made it.

That last column is why the licence number is copied onto the record at the
time rather than looked up now. Somebody who renewed in March has a different
number than they had in February, and February's report has to go on saying
what it said.

A row missing any of those columns is not filed short. It is held back and
counted, because a return with a blank in it comes back with a letter.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import rules
from dipcount.model.product import Product
from dipcount.report.sheet import Sheet, table
from dipcount.store import blocks, products, runs, sites, treatments
from dipcount.store.book import Book
from dipcount.units import COUNT, Quantity

COLUMNS = (
    "day",
    "record",
    "place",
    "kind",
    "product",
    "registration",
    "active",
    "percent",
    "amount",
    "area",
    "rate",
    "applicator",
    "licence",
    "restricted",
)


@dataclass(frozen=True)
class Line:
    """One application as the state wants to read it."""

    on: dt.date
    record: str
    place: str
    kind: str
    product: Product
    amount: Quantity
    area: Quantity
    applicator: str
    licence: str

    @property
    def rate(self) -> str:
        """What went on per unit of area."""
        if self.area.amount == 0:
            return "-"
        return f"{(self.amount / self.area.amount)}/{self.area.unit}"

    @property
    def active_applied(self) -> Quantity:
        """How much active ingredient this line put down."""
        return self.product.active_in(self.amount)

    @property
    def complete(self) -> bool:
        """Whether the row has everything the return needs."""
        return bool(
            self.record
            and self.place
            and self.product.registration
            and self.applicator
            and self.licence
            and self.amount.amount > 0
            and self.area.amount > 0,
        )

    def cells(self) -> list[str]:
        """The row, in the order the columns are declared."""
        return [
            self.on.isoformat(),
            self.record,
            self.place,
            self.kind,
            self.product.name,
            self.product.registration,
            self.product.active,
            f"{self.product.percent:g}",
            str(self.amount),
            str(self.area),
            self.rate,
            self.applicator,
            self.licence,
            "yes" if self.product.restricted else "",
        ]


@dataclass(frozen=True)
class Return:
    """Every application over a window, ready to file."""

    start: dt.date
    end: dt.date
    lines: tuple[Line, ...] = field(default_factory=tuple)

    @property
    def filed(self) -> list[Line]:
        """Every row with nothing missing."""
        return [one for one in self.lines if one.complete]

    @property
    def held(self) -> list[Line]:
        """Every row the return cannot carry."""
        return [one for one in self.lines if not one.complete]

    def sheet(self) -> Sheet:
        """The return as a table."""
        return table(
            list(COLUMNS),
            [one.cells() for one in self.filed],
            title=f"pesticide use, {self.start} to {self.end}",
        )

    def csv(self) -> str:
        """The return as comma separated values."""
        return self.sheet().csv()

    def by_product(self) -> dict[str, Quantity]:
        """How much of each product went out over the window."""
        out: dict[str, Quantity] = {}
        for one in self.filed:
            held = out.get(one.product.name)
            out[one.product.name] = one.amount if held is None else held + one.amount.to(held.unit)
        return out

    def by_active(self) -> dict[str, Quantity]:
        """How much of each active ingredient went out, where it can be said.

        A product measured one structure at a time is left out. A share of a
        pouch is a share of a pouch, and until the district records what a
        pouch weighs there is no honest way to add it into a total in pounds.
        Those lines come back from :meth:`counted_actives` instead, so a
        return that leaves them out says so rather than losing them.
        """
        out: dict[str, Quantity] = {}
        for one in self.filed:
            if one.amount.dimension == COUNT:
                continue
            applied = one.active_applied
            held = out.get(one.product.active)
            out[one.product.active] = applied if held is None else held + applied.to(held.unit)
        return out

    def counted_actives(self) -> dict[str, Quantity]:
        """The applications whose amount is a count of structures."""
        out: dict[str, Quantity] = {}
        for one in self.filed:
            if one.amount.dimension != COUNT:
                continue
            held = out.get(one.product.active)
            out[one.product.active] = (
                one.amount if held is None else held + one.amount.to(held.unit)
            )
        return out

    def restricted(self) -> list[Line]:
        """Every application of a restricted use product."""
        return [one for one in self.filed if one.product.restricted]

    def totals_sheet(self) -> Sheet:
        """Product and active ingredient totals."""
        rows: list[list[str]] = []
        for name, amount in sorted(self.by_product().items()):
            rows.append(["product", name, str(amount)])
        for name, amount in sorted(self.by_active().items()):
            rows.append(["active", name, str(amount)])
        for name, amount in sorted(self.counted_actives().items()):
            rows.append(["not weighable", name, str(amount)])
        return table(["what", "name", "total"], rows, title="totals")

    def render(self) -> str:
        """The whole return as text."""
        pieces = [self.sheet().render(), self.totals_sheet().render()]
        if self.held:
            pieces.append(
                table(
                    ["record", "why"],
                    [[one.record, "a column the return needs is empty"] for one in self.held],
                    title="held back",
                ).render(),
            )
        return "\n\n".join(pieces)


def _treatment_lines(book: Book, start: dt.date, end: dt.date) -> list[Line]:
    out: list[Line] = []
    for one in treatments.between(book, start, end):
        site = sites.get(book, one.site)
        product = products.get(book, one.product)
        out.append(
            Line(
                on=one.on,
                record=one.id,
                place=f"{site.id} {site.name}",
                kind=site.kind.name,
                product=product,
                amount=one.amount,
                area=one.extent,
                applicator=one.applicator,
                licence=one.licence,
            ),
        )
    return out


def _run_lines(book: Book, start: dt.date, end: dt.date) -> list[Line]:
    out: list[Line] = []
    for one in runs.between(book, start, end):
        block = blocks.get(book, one.block)
        product = products.get(book, one.product)
        out.append(
            Line(
                on=one.on,
                record=one.id,
                place=f"{block.id} {block.name}",
                kind="spray block",
                product=product,
                amount=one.amount,
                area=Quantity(Decimal(str(one.acres)), "acre"),
                applicator=one.applicator,
                licence=one.licence,
            ),
        )
    return out


def use_return(book: Book, start: dt.date, end: dt.date) -> Return:
    """Gather every application over a window."""
    lines = _treatment_lines(book, start, end) + _run_lines(book, start, end)
    lines.sort(key=lambda one: (one.on, one.record))
    return Return(start=start, end=end, lines=tuple(lines))


def season(book: Book, year: int) -> Return:
    """Every application in one calendar season."""
    return use_return(book, dt.date(year, 1, 1), dt.date(year, 12, 31))


def keep_until(year: int) -> dt.date:
    """The earliest day a season's records may be destroyed."""
    return dt.date(year + rules.RETENTION_YEARS, 12, 31)


def destroyable(year: int, on: dt.date) -> bool:
    """Whether a season's records are past their retention."""
    return on > keep_until(year)
