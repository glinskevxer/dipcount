"""Who may make an application, and who is going to lose their licence.

Two questions that look like one. "May this person put this product in this
water today" is about the licence date, the category and the grade, and the
answer changes with the product and the site. "Will this person be renewed" is
about credit hours over a three year cycle, and the answer has no bearing at
all on today's work.

The category is the part that composes. The work decides which category is
needed: permanent water needs the aquatic category, everything else in this
programme needs public health. So a licence that covers one site does not
cover the next one along, and a report that asks only whether somebody is
licensed has not asked the question.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import habitat as hb
from dipcount.model.applicator import AQUATIC, PUBLIC_HEALTH, Applicator
from dipcount.model.product import ADULTICIDE, Product
from dipcount.model.site import Site
from dipcount.rules import Refusal
from dipcount.store import applicators, products, sites
from dipcount.store.book import Book


@dataclass(frozen=True)
class Standing:
    """Where one licence holder stands on a given day."""

    applicator: Applicator
    on: dt.date
    hours_held: Decimal
    hours_needed: Decimal
    by_category: dict[str, Decimal] = field(default_factory=dict)

    @property
    def licensed(self) -> bool:
        """Whether the licence is in date today."""
        return self.applicator.licensed(self.on)

    @property
    def days_left(self) -> int:
        """How many days until the licence expires."""
        return (self.applicator.expires_on - self.on).days

    @property
    def hours_short(self) -> Decimal:
        """How many credit hours are still wanted before renewal."""
        short = self.hours_needed - self.hours_held
        return short if short > 0 else Decimal(0)

    @property
    def renewable(self) -> bool:
        """Whether the credits are in place for a renewal."""
        return self.hours_short == 0

    def line(self) -> str:
        """One line for a licence sheet."""
        state = "in date" if self.licensed else "expired"
        hours = "credits met" if self.renewable else f"{self.hours_short} hours short"
        return (
            f"{self.applicator.id}  {self.applicator.name}  {self.applicator.grade}"
            f"  {state} to {self.applicator.expires_on}  {hours}"
        )


def category_for(site: Site, product: Product) -> str:
    """Which licence category one application needs.

    Adulticiding is public health work wherever it happens. Larviciding into
    permanent water is aquatic work, and larviciding anything that dries up is
    not.
    """
    if product.purpose == ADULTICIDE:
        return PUBLIC_HEALTH
    return AQUATIC if site.kind.permanence == hb.PERMANENT else PUBLIC_HEALTH


def standing(book: Book, applicator_id: str, on: dt.date) -> Standing:
    """Where somebody stands on licence and on credits."""
    holder = applicators.resolve(book, applicator_id)
    earned = applicators.credits_for(
        book,
        holder.id,
        since=holder.cycle_start(),
        until=holder.expires_on,
    )
    by_category: dict[str, Decimal] = {}
    for one in earned:
        by_category[one.category] = by_category.get(one.category, Decimal(0)) + one.hours
    return Standing(
        applicator=holder,
        on=on,
        hours_held=sum(by_category.values(), Decimal(0)),
        hours_needed=holder.hours_needed,
        by_category=by_category,
    )


def check(
    book: Book,
    applicator_id: str,
    site_id: str,
    product_id: str,
    on: dt.date,
) -> Refusal | None:
    """Say whether somebody may make one application, and why not if not."""
    holder = applicators.resolve(book, applicator_id)
    site = sites.get(book, site_id)
    product = products.resolve(book, product_id)
    wanted = category_for(site, product)
    if not holder.licensed(on):
        return Refusal(
            "licence.date",
            f"{holder.name} is licensed {holder.certified_on} to {holder.expires_on}",
        )
    if not holder.covers(wanted):
        return Refusal(
            "licence.category",
            f"{holder.name} does not hold the {wanted} category",
        )
    if not holder.may_apply(on, wanted, restricted=product.restricted):
        return Refusal(
            "licence.grade",
            f"{product.name} is restricted and {holder.name} is a {holder.grade}",
        )
    return None


def may_apply(
    book: Book,
    applicator_id: str,
    site_id: str,
    product_id: str,
    on: dt.date,
) -> bool:
    """Whether somebody may make one application."""
    return check(book, applicator_id, site_id, product_id, on) is None


def crew(book: Book, site_id: str, product_id: str, on: dt.date) -> list[Applicator]:
    """Everybody who could legally make one application today."""
    return [
        one
        for one in applicators.working(book, on)
        if may_apply(book, one.id, site_id, product_id, on)
    ]


def expiring(book: Book, on: dt.date, days: int = 90) -> list[Standing]:
    """Every licence that runs out inside a window, soonest first."""
    out = [
        standing(book, one.id, on)
        for one in applicators.all_applicators(book)
        if one.left_on is None and 0 <= (one.expires_on - on).days <= days
    ]
    return sorted(out, key=lambda one: one.days_left)


def short_of_credits(book: Book, on: dt.date) -> list[Standing]:
    """Everybody working who will not be renewed on today's hours."""
    return [
        one
        for one in (standing(book, holder.id, on) for holder in applicators.working(book, on))
        if not one.renewable
    ]


def board(book: Book, on: dt.date) -> list[Standing]:
    """Where everybody stands, by id."""
    return [standing(book, one.id, on) for one in applicators.all_applicators(book)]
