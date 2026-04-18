"""Deciding what may go into a piece of water, and then putting it there.

This is where the label, the season and the shelf meet, and the order they
meet in matters. The label gives a rate range for the habitat. The season cap
says how much that acre may take in a year, and what earlier treatments have
already used of it. Between them they decide the rate this application may
use, which is not the same as either.

The case worth understanding is a season cap that has almost run out. It does
not produce a smaller treatment. If what is left of the cap divided over the
ground comes to less than the bottom of the label's range, then there is no
legal application left to make at that site with that product this season, and
the answer is to use something else or to leave it. Reading the cap as a
ceiling on the amount, and quietly applying what fits under it, is how a
district ends up with a season of applications that were all under strength.

Every refusal names its clause, so a plan that cannot go ahead says which line
of the rule book stopped it rather than just saying no.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import clock
from dipcount.errors import RuleViolation
from dipcount.model.applicator import Applicator
from dipcount.model.lot import APPLIED, Lot
from dipcount.model.product import Label, Product
from dipcount.model.site import Site
from dipcount.model.treatment import Treatment
from dipcount.rules import Refusal
from dipcount.service import licensing
from dipcount.store import applicators, audit, inventory, products, sites, treatments
from dipcount.store.book import Book
from dipcount.units import Quantity, Rate

LOW = "low"
MIDDLE = "middle"
HIGH = "high"
STRENGTHS = (LOW, MIDDLE, HIGH)


@dataclass(frozen=True)
class Plan:
    """What would go on, and what stops it if anything does."""

    site: str
    product: str
    on: dt.date
    extent: Quantity
    rate: Rate | None = None
    amount: Quantity | None = None
    season_used: Quantity | None = None
    season_left: Quantity | None = None
    refusals: tuple[Refusal, ...] = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        """Whether this application may be made."""
        return not self.refusals and self.amount is not None

    def check(self) -> None:
        """Raise the first refusal, if there is one."""
        if self.refusals:
            self.refusals[0].raise_it()

    def line(self) -> str:
        """One line for a work order."""
        if not self.allowed:
            return f"{self.site}  {self.product}  refused: {self.refusals[0].detail}"
        return f"{self.site}  {self.product}  {self.amount} at {self.rate} over {self.extent}"


def _label_of(product: Product, site: Site) -> Label | None:
    return product.label_for(site.habitat)


def _rate_at(label: Label, strength: str) -> Rate:
    if strength == LOW:
        return label.low
    if strength == HIGH:
        return label.high
    return label.middle()


def _under_the_cap(
    book: Book,
    site: Site,
    product: Product,
    label: Label,
    on: dt.date,
    over: Quantity,
    wanted: Rate,
) -> tuple[Rate, Quantity, Quantity | None, Quantity | None, Refusal | None]:
    """Bring a rate down to what the season leaves, and say if it cannot be."""
    used, left_rate = _season(book, site, product, label, on)
    left = None if left_rate is None else left_rate.over(over)
    amount = wanted.over(over)
    if left is not None and amount > left:
        wanted, amount, capped = _fit_to_cap(label, over, left)
        return wanted, amount, used, left, capped
    return wanted, amount, used, left, None


def _off_label(label: Label, wanted: Rate) -> Refusal:
    """The refusal a rate outside the labelled range earns."""
    return Refusal(
        "label.rate",
        f"{wanted} is outside {label.low.amount} to {label.high.amount} per {label.per}",
    )


def _standing_refusals(
    site: Site,
    product: Product,
    over: Quantity,
    on: dt.date,
) -> list[Refusal]:
    """Everything that stops an application before the label is read at all."""
    out: list[Refusal] = []
    if not site.is_open(on):
        out.append(Refusal("site.retired", f"{site.id} was not on the list on {on}"))
    if not product.on_shelf(on):
        out.append(Refusal("label.shelf", f"{product.name} was not on the shelf on {on}"))
    if not site.kind.allows(product.form):
        out.append(Refusal("label.form", f"a {site.kind.name} does not take a {product.form}"))
    if over.unit == site.extent.unit and over > site.extent:
        out.append(
            Refusal("treat.extent", f"{site.id} is {site.extent} and {over} was asked for"),
        )
    return out


def plan(
    book: Book,
    site_id: str,
    product_id: str,
    on: dt.date,
    *,
    extent: Quantity | None = None,
    strength: str = MIDDLE,
    rate: Rate | None = None,
) -> Plan:
    """Work out what may go on a site, and say what stops it if anything does."""
    site = sites.get(book, site_id)
    product = products.resolve(book, product_id)
    over = extent if extent is not None else site.extent
    refusals = _standing_refusals(site, product, over, on)

    label = _label_of(product, site)
    if label is None:
        refusals.append(
            Refusal("label.site", f"{product.name} is not labelled for a {site.kind.name}"),
        )
        return Plan(site.id, product.id, on, over, refusals=tuple(refusals))

    if over.unit != site.extent.unit:
        refusals.append(
            Refusal("treat.extent", f"a {site.kind.name} is measured in {site.extent.unit}"),
        )
        return Plan(site.id, product.id, on, over, refusals=tuple(refusals))

    gap = _interval_refusal(book, site, product, label, on)
    if gap is not None:
        refusals.append(gap)

    wanted = rate if rate is not None else _rate_at(label, strength)
    if not label.covers(wanted):
        refusals.append(_off_label(label, wanted))
        return Plan(site.id, product.id, on, over, rate=wanted, refusals=tuple(refusals))

    wanted, amount, used, left, capped = _under_the_cap(
        book, site, product, label, on, over, wanted
    )
    if capped is not None:
        refusals.append(capped)

    return Plan(
        site=site.id,
        product=product.id,
        on=on,
        extent=over,
        rate=wanted,
        amount=amount,
        season_used=used,
        season_left=left,
        refusals=tuple(refusals),
    )


def _fit_to_cap(
    label: Label,
    over: Quantity,
    left: Quantity,
) -> tuple[Rate, Quantity, Refusal | None]:
    """Bring a rate down to what the season cap leaves, if that is legal."""
    if left.amount <= 0:
        return (
            label.low,
            left,
            Refusal(
                "label.season",
                f"the season cap of {label.season_max} per {label.per} is used up",
            ),
        )
    reduced = Rate(left / over.amount, label.per)
    if not label.covers(reduced):
        return (
            reduced,
            left,
            Refusal(
                "label.season",
                f"{left} left of the season cap over {over} works out at"
                f" {reduced}, under the labelled minimum of"
                f" {label.low.amount} per {label.per}",
            ),
        )
    return reduced, left, None


def _season(
    book: Book,
    site: Site,
    product: Product,
    label: Label,
    on: dt.date,
) -> tuple[Quantity | None, Rate | None]:
    """What the season has used at this site, and what is left of the cap.

    Both are per unit of extent, because that is how the cap is written. A
    six acre marsh that has taken sixty pounds has taken ten pounds an acre,
    and the cap does not care that the whole was sixty.
    """
    if label.season_max is None:
        return None, None
    unit = label.season_max.unit
    used = treatments.season_total(book, site.id, product.id, on.year, unit=unit)
    per_unit = Quantity(used.amount / site.extent.to(label.per).amount, unit)
    return used, Rate(label.season_max - per_unit, label.per)


def _interval_refusal(
    book: Book,
    site: Site,
    product: Product,
    label: Label,
    on: dt.date,
) -> Refusal | None:
    if label.interval_days <= 0:
        return None
    last = treatments.last_at(book, site.id, product_id=product.id, on=on)
    if last is None:
        return None
    waited = (on - last.on).days
    if waited < label.interval_days:
        return Refusal(
            "label.interval",
            f"{product.name} went on {site.id} {waited} days ago"
            f" and the label wants {label.interval_days}",
        )
    return None


def _lot_refusals(book: Book, lot: Lot, product: Product, on: dt.date, amount: Quantity) -> None:
    if lot.product != product.id:
        raise RuleViolation("stock.product", f"{lot.id} is not a lot of {product.name}")
    if lot.expired(on):
        raise RuleViolation("stock.expired", f"{lot.id} went out of date on {lot.expires_on}")
    holding = inventory.stock(book, lot.id)
    if amount.dimension != holding.lot.quantity.dimension:
        raise RuleViolation("stock.unit", f"{lot.id} is measured in {lot.quantity.unit}")
    if not holding.can_take(amount):
        raise RuleViolation(
            "stock.short",
            f"{lot.id} has {holding.left} left and {amount} was asked for",
        )


def treat(
    book: Book,
    applicator_id: str,
    site_id: str,
    lot_id: str,
    at: dt.datetime,
    *,
    product_id: str | None = None,
    extent: Quantity | None = None,
    strength: str = MIDDLE,
    rate: Rate | None = None,
    equipment: str = "",
    inspection: str | None = None,
    note: str = "",
) -> Treatment:
    """Make one application, drawing the product off a lot.

    The product is read off the lot rather than typed in beside it. A caller
    that has both on a work card can pass ``product_id`` as well, and the two
    are checked against each other before anything else happens.

    The applicator is a licence holder, not a name typed on a card. Whether
    they may make this particular application depends on the site and the
    product as much as on the licence, so the check happens here where all
    three are to hand.
    """
    holder = applicators.resolve(book, applicator_id)
    lot = inventory.get(book, lot_id)
    product = products.get(book, lot.product)
    if product_id is not None and products.resolve(book, product_id).id != product.id:
        raise RuleViolation(
            "stock.product",
            f"{lot.id} is not a lot of {product_id}, it is a lot of {product.name}",
        )
    on = clock.in_zone(at).date()
    made = plan(book, site_id, product.id, on, extent=extent, strength=strength, rate=rate)
    made.check()
    refused = licensing.check(book, holder.id, site_id, product.id, on)
    if refused is not None:
        refused.raise_it()
    assert made.amount is not None
    _lot_refusals(book, lot, product, on, made.amount)
    return _record(
        book,
        holder,
        site_id,
        lot,
        product,
        at,
        made,
        equipment=equipment,
        inspection=inspection,
        note=note,
    )


def _record(
    book: Book,
    holder: Applicator,
    site_id: str,
    lot: Lot,
    product: Product,
    at: dt.datetime,
    made: Plan,
    *,
    equipment: str,
    inspection: str | None,
    note: str,
) -> Treatment:
    """Write the treatment, draw the product, and leave the trail line."""
    assert made.amount is not None
    with book.writing():
        record = treatments.write(
            book,
            site_id,
            lot.id,
            at,
            holder.name,
            made.extent,
            made.amount,
            licence=holder.licence,
            equipment=equipment,
            inspection=inspection,
            note=note,
        )
        inventory.draw(
            book,
            lot.id,
            made.amount,
            at,
            holder.name,
            reason=APPLIED,
            reference=record.id,
        )
        audit.record(
            book,
            holder.name,
            "treated",
            site_id,
            f"{record.id}: {made.amount} of {product.name} at {made.rate}",
            at=at,
        )
    return record


def choices(book: Book, site_id: str, on: dt.date) -> list[Plan]:
    """Every product that could legally go on a site today, best first."""
    site = sites.get(book, site_id)
    out: list[Plan] = []
    for product in products.for_habitat(book, site.habitat, on=on):
        out.append(plan(book, site.id, product.id, on))
    return sorted(out, key=lambda one: (not one.allowed, one.product))


def active_applied(book: Book, site_id: str, year: int) -> dict[str, Quantity]:
    """How much of each active ingredient a site took in a season."""
    out: dict[str, Quantity] = {}
    for one in treatments.between(
        book,
        dt.date(year, 1, 1),
        dt.date(year, 12, 31),
        site_id=site_id,
    ):
        product = products.get(book, one.product)
        active = one.active(Decimal(str(product.percent)))
        if product.active in out:
            out[product.active] = out[product.active] + active
        else:
            out[product.active] = active
    return out
