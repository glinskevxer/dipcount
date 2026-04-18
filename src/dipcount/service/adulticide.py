"""Whether a block may be fogged tonight, and recording it when it is.

Four separate things have to line up and none of them is negotiable, so they
are checked together and reported together rather than one at a time. A
supervisor standing in the yard at half past eight wants the whole list, not
the first thing that failed.

The wind is a band and not a ceiling. Too much and the fog leaves the block;
too little and there is nothing to carry the droplets, an inversion sits over
the street, and the whole load ends up where it was released. Crews learn the
ceiling and forget the floor, and a still night reads like a perfect one.

Notice is the part that composes. Which places have to be told comes from the
block. How much warning each of them wants comes from the kind of entry it is.
Whether they were told in time comes from the notice, the entry and the run's
own start time together, so the same notice is good for a run at ten and not
for one at midnight if the window closed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import clock, rules
from dipcount.model.applicator import PUBLIC_HEALTH, Applicator
from dipcount.model.block import Block, Notice, Run
from dipcount.model.exclusion import Exclusion
from dipcount.model.lot import Lot
from dipcount.model.product import ADULTICIDE, Product
from dipcount.rules import Refusal
from dipcount.store import applicators, audit, blocks, inventory, products, runs
from dipcount.store.book import Book
from dipcount.units import Quantity


@dataclass(frozen=True)
class Window:
    """Whether one block may be run at one moment, and what stops it."""

    block: str
    at: dt.datetime
    acres: float
    wind_mph: Decimal | None = None
    temperature: Decimal | None = None
    told: tuple[str, ...] = field(default_factory=tuple)
    untold: tuple[str, ...] = field(default_factory=tuple)
    barred: tuple[str, ...] = field(default_factory=tuple)
    refusals: tuple[Refusal, ...] = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        """Whether the truck may go out."""
        return not self.refusals

    def check(self) -> None:
        """Raise the first refusal, if there is one."""
        if self.refusals:
            self.refusals[0].raise_it()

    def line(self) -> str:
        """One line for a night sheet."""
        if self.allowed:
            return f"{self.block}  {clock.stamp(self.at)}  clear, {len(self.told)} told"
        return f"{self.block}  {clock.stamp(self.at)}  held: {self.refusals[0].rule}"


def _weather_refusals(
    wind_mph: Decimal | None,
    temperature: Decimal | None,
) -> list[Refusal]:
    out: list[Refusal] = []
    if wind_mph is None:
        out.append(Refusal("spray.wind", "no wind reading was taken"))
    elif wind_mph < rules.WIND_LOW:
        out.append(
            Refusal(
                "spray.wind",
                f"{wind_mph} mph is under the {rules.WIND_LOW} mph floor,"
                " which is an inversion rather than a still night",
            ),
        )
    elif wind_mph > rules.WIND_HIGH:
        out.append(
            Refusal("spray.wind", f"{wind_mph} mph is over the {rules.WIND_HIGH} mph ceiling"),
        )
    if temperature is None:
        out.append(Refusal("spray.temperature", "no temperature reading was taken"))
    elif temperature < rules.TEMP_FLOOR:
        out.append(
            Refusal(
                "spray.temperature",
                f"{temperature} degrees is under the {rules.TEMP_FLOOR} degree floor",
            ),
        )
    return out


def _hours_refusal(at: dt.datetime, zone: str) -> Refusal | None:
    hour = clock.in_zone(at, zone).hour
    if hour >= rules.NIGHT_FROM or hour < rules.NIGHT_TO:
        return None
    return Refusal(
        "spray.hours",
        f"{clock.stamp(at, zone)} is outside the {rules.NIGHT_FROM} to {rules.NIGHT_TO} window",
    )


def _notice_state(
    book: Book,
    block: Block,
    at: dt.datetime,
) -> tuple[list[Exclusion], list[tuple[Exclusion, Notice | None]], list[Exclusion]]:
    """Split a block's register entries into barred, told and untold."""
    on = clock.in_zone(at).date()
    barred: list[Exclusion] = []
    told: list[tuple[Exclusion, Notice | None]] = []
    untold: list[Exclusion] = []
    for entry in blocks.entries_in(book, block.id, on):
        if entry.absolute:
            barred.append(entry)
            continue
        notice = blocks.covering(book, block.id, entry.id, at)
        if notice is None or notice.hours_given < entry.hours:
            untold.append(entry)
        else:
            told.append((entry, notice))
    return barred, told, untold


def window(
    book: Book,
    block_id: str,
    at: dt.datetime,
    *,
    wind_mph: float | None = None,
    temperature: float | None = None,
    acres: float | None = None,
    zone: str = clock.DEFAULT_ZONE,
) -> Window:
    """Say whether a block may be run at a moment, and what stops it."""
    block = blocks.resolve(book, block_id)
    over = block.acres if acres is None else acres
    wind = None if wind_mph is None else Decimal(str(wind_mph))
    warmth = None if temperature is None else Decimal(str(temperature))
    refusals: list[Refusal] = []

    if not block.is_open(clock.in_zone(at, zone).date()):
        refusals.append(Refusal("spray.block", f"{block.id} is not on the run list"))
    if over <= 0 or over > block.acres:
        refusals.append(
            Refusal("spray.acres", f"{block.id} is {block.acres:g} acre and {over:g} was asked"),
        )
    hours = _hours_refusal(at, zone)
    if hours is not None:
        refusals.append(hours)
    refusals.extend(_weather_refusals(wind, warmth))

    barred, told, untold = _notice_state(book, block, at)
    for entry in barred:
        refusals.append(
            Refusal("spray.absolute", f"{entry.name} is {entry.kind} and takes the block off"),
        )
    for entry in untold:
        refusals.append(
            Refusal(
                "spray.notice",
                f"{entry.name} wants {entry.hours} hours notice and has not had it",
            ),
        )
    return Window(
        block=block.id,
        at=at,
        acres=over,
        wind_mph=wind,
        temperature=warmth,
        told=tuple(entry.id for entry, _ in told),
        untold=tuple(entry.id for entry in untold),
        barred=tuple(entry.id for entry in barred),
        refusals=tuple(refusals),
    )


def spray(
    book: Book,
    applicator_id: str,
    block_id: str,
    lot_id: str,
    started_at: dt.datetime,
    finished_at: dt.datetime,
    amount: Quantity,
    *,
    acres: float | None = None,
    wind_mph: float | None = None,
    temperature: float | None = None,
    wind_from: str = "",
    equipment: str = "",
    note: str = "",
) -> Run:
    """Record one night's run, having checked it may be made."""
    holder = applicators.resolve(book, applicator_id)
    block = blocks.resolve(book, block_id)
    lot = inventory.get(book, lot_id)
    product = products.get(book, lot.product)
    tonight = window(
        book,
        block.id,
        started_at,
        wind_mph=wind_mph,
        temperature=temperature,
        acres=acres,
    )
    _refuse_the_run(holder, lot, product, started_at, tonight)
    return _record_run(
        book,
        holder,
        block,
        lot,
        product,
        started_at,
        finished_at,
        amount,
        tonight,
        equipment=equipment,
        temperature=temperature,
        wind_mph=wind_mph,
        wind_from=wind_from,
        note=note,
    )


def _refuse_the_run(
    holder: Applicator,
    lot: Lot,
    product: Product,
    started_at: dt.datetime,
    tonight: Window,
) -> None:
    """Raise the first thing that stops this run, if anything does."""
    if product.purpose != ADULTICIDE:
        Refusal(
            "label.site",
            f"{product.name} is a {product.purpose} and does not go through a fogger",
        ).raise_it()
    tonight.check()
    on = clock.in_zone(started_at).date()
    if not holder.licensed(on) or not holder.may_apply(
        on,
        PUBLIC_HEALTH,
        restricted=product.restricted,
    ):
        Refusal(
            "licence.grade",
            f"{holder.name} may not apply {product.name} on {on.isoformat()}",
        ).raise_it()
    if lot.expired(on):
        Refusal("stock.expired", f"{lot.id} went out of date on {lot.expires_on}").raise_it()


def _record_run(
    book: Book,
    holder: Applicator,
    block: Block,
    lot: Lot,
    product: Product,
    started_at: dt.datetime,
    finished_at: dt.datetime,
    amount: Quantity,
    tonight: Window,
    *,
    equipment: str,
    temperature: float | None,
    wind_mph: float | None,
    wind_from: str,
    note: str,
) -> Run:
    """Write the run, draw the product, and leave the trail line."""
    with book.writing():
        made = runs.write(
            book,
            block.id,
            lot.id,
            holder.name,
            started_at,
            finished_at,
            amount,
            tonight.acres,
            licence=holder.licence,
            equipment=equipment,
            temperature=temperature,
            wind_mph=wind_mph,
            wind_from=wind_from,
            note=note,
        )
        inventory.draw(book, lot.id, amount, started_at, holder.name, reference=made.id)
        audit.record(
            book,
            holder.name,
            "sprayed",
            block.id,
            f"{made.id}: {amount} over {tonight.acres:g} acre of {product.name}",
            at=started_at,
        )
    return made


def tonight_board(
    book: Book,
    at: dt.datetime,
    *,
    wind_mph: float | None = None,
    temperature: float | None = None,
    zone_id: str | None = None,
) -> list[Window]:
    """Every block and whether it may be run at a moment."""
    on = clock.in_zone(at).date()
    return [
        window(book, one.id, at, wind_mph=wind_mph, temperature=temperature)
        for one in blocks.open_on(book, on, zone_id=zone_id)
    ]


def who_to_tell(book: Book, block_id: str, at: dt.datetime) -> list[Exclusion]:
    """Everybody inside a block who has not been told about this run."""
    block = blocks.resolve(book, block_id)
    _, _, untold = _notice_state(book, block, at)
    return untold


def notice_deadline(book: Book, block_id: str, at: dt.datetime) -> dt.datetime | None:
    """The latest moment notice could still be given for a run at ``at``."""
    on = clock.in_zone(at).date()
    entries = [
        one
        for one in blocks.entries_in(book, blocks.resolve(book, block_id).id, on)
        if not one.absolute
    ]
    if not entries:
        return None
    return min(one.notice_by(at) for one in entries)


def register_in(book: Book, block_id: str, on: dt.date) -> list[Exclusion]:
    """Every register entry inside a block on a day."""
    return blocks.entries_in(book, blocks.resolve(book, block_id).id, on)
