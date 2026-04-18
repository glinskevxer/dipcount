"""What the bottle assays mean for what the district should be spraying.

A finding is narrower than it looks. It is about one active ingredient against
one species from one place at one time, and every one of those four qualifiers
has to survive the journey to a decision. Resistance in catch basin Culex is
not a reason to change what goes on a floodplain producing Aedes, and a
finding from three seasons ago is history.

What it is wider than is the product. Two bottles of different brand names
holding the same mode of action are one thing to a mosquito, so the rotation
that matters is over modes and not over labels. A district that alternates two
bacterial toxins every fortnight has not rotated anything.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dipcount import rules, species
from dipcount.errors import NotFound
from dipcount.model.bioassay import POSSIBLE, RESISTANT, VOID, Bioassay
from dipcount.model.product import Product
from dipcount.rules import Refusal
from dipcount.store import bioassays, products, sites, treatments
from dipcount.store.book import Book


@dataclass(frozen=True)
class Finding:
    """What the latest assay says about one active against one species."""

    active: str
    species: str
    on: dt.date
    assay: Bioassay | None = None
    zone: str | None = None

    @property
    def verdict(self) -> str:
        """What the assay said, or nothing if there has not been one."""
        return "untested" if self.assay is None else self.assay.verdict()

    @property
    def age_days(self) -> int | None:
        """How old the finding is, in days."""
        return None if self.assay is None else (self.on - self.assay.on).days

    @property
    def stale(self) -> bool:
        """Whether the finding is old enough to be history rather than evidence."""
        age = self.age_days
        return age is not None and age > rules.STALE_DAYS

    @property
    def suspect(self) -> bool:
        """Whether this active is in doubt against this species."""
        if self.assay is None or self.stale:
            return False
        return self.verdict in (RESISTANT, POSSIBLE)

    @property
    def reasons(self) -> tuple[str, ...]:
        """The clauses that decided what this finding is worth."""
        out = ["resistance.species"]
        if self.stale:
            out.append("resistance.stale")
        return tuple(out)

    @property
    def mode(self) -> str | None:
        """The mode of action this active belongs to, if it is known."""
        try:
            return rules.mode_of(self.active)
        except NotFound:
            return None

    def line(self) -> str:
        """One line for a resistance sheet."""
        if self.assay is None:
            return f"{self.active} against {self.species}: untested"
        age = f", {self.age_days} days old" if self.age_days else ""
        old = " (stale)" if self.stale else ""
        return f"{self.active} against {self.species}: {self.verdict}{age}{old}"


def standing(
    book: Book,
    active: str,
    code: str,
    on: dt.date,
    *,
    zone_id: str | None = None,
) -> Finding:
    """The latest assay of one active against one species, as of a day.

    A void assay is not a finding. It is a run that failed, and the answer is
    whatever the last readable run said.
    """
    for one in reversed(bioassays.all_assays(book, active=active, code=code, zone_id=zone_id)):
        if one.on <= on and one.verdict() != VOID:
            return Finding(active=active, species=code, on=on, assay=one, zone=zone_id)
    return Finding(active=active, species=code, on=on, zone=zone_id)


def board(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[Finding]:
    """Every active and species pair anything has been run on."""
    out: list[Finding] = []
    for one in bioassays.all_assays(book, zone_id=zone_id):
        pair = (one.active, one.species)
        if any((two.active, two.species) == pair for two in out):
            continue
        out.append(standing(book, one.active, one.species, on, zone_id=zone_id))
    return sorted(out, key=lambda one: (one.active, one.species))


def suspect_actives(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[str]:
    """Every active ingredient in doubt somewhere, in name order."""
    return sorted({one.active for one in board(book, on, zone_id=zone_id) if one.suspect})


def bearing_on(book: Book, site_id: str, product_id: str, on: dt.date) -> list[Finding]:
    """Every finding that actually bears on treating one site with one product.

    Only the species the site's habitat produces count. A finding against a
    species that could never be in that water is a finding about somewhere
    else.
    """
    site = sites.get(book, site_id)
    product = products.resolve(book, product_id)
    here = {one.code for one in site.kind.species_here()}
    found = [standing(book, product.active, code, on, zone_id=site.zone) for code in sorted(here)]
    return [one for one in found if one.assay is not None]


def warn(book: Book, site_id: str, product_id: str, on: dt.date) -> Refusal | None:
    """A warning if the product is in doubt against what this water makes."""
    doubtful = [one for one in bearing_on(book, site_id, product_id, on) if one.suspect]
    if not doubtful:
        return None
    first = doubtful[0]
    return Refusal(
        "resistance.species",
        f"{first.active} read {first.verdict} against {first.species}"
        f" on {first.assay.on if first.assay else 'an unknown day'}",
    )


def rotation(book: Book, site_id: str, on: dt.date, *, back: int = 5) -> list[str]:
    """The modes of action last used at a site, most recent last."""
    out: list[str] = []
    for one in treatments.for_site(book, site_id):
        if one.on > on:
            continue
        product = products.get(book, one.product)
        try:
            out.append(rules.mode_of(product.active))
        except NotFound:
            out.append("unknown")
    return out[-back:]


def rotation_warning(
    book: Book,
    site_id: str,
    product_id: str,
    on: dt.date,
) -> Refusal | None:
    """A warning if this product would repeat one mode of action too often."""
    product = products.resolve(book, product_id)
    try:
        mode = rules.mode_of(product.active)
    except NotFound:
        return None
    run = 0
    for one in reversed(rotation(book, site_id, on)):
        if one != mode:
            break
        run += 1
    if run + 1 >= rules.ROTATION_RUN:
        return Refusal(
            "resistance.rotation",
            f"{mode} would be {run + 1} applications running at {site_id}",
        )
    return None


def alternatives(book: Book, site_id: str, product_id: str, on: dt.date) -> list[Product]:
    """Every labelled product for the site in a different mode of action."""
    site = sites.get(book, site_id)
    product = products.resolve(book, product_id)
    try:
        mode = rules.mode_of(product.active)
    except NotFound:
        mode = ""
    out: list[Product] = []
    for one in products.for_habitat(book, site.habitat, on=on):
        if one.id == product.id:
            continue
        try:
            other = rules.mode_of(one.active)
        except NotFound:
            continue
        if other != mode:
            out.append(one)
    return out


def coverage(book: Book, on: dt.date) -> dict[str, list[str]]:
    """Which species each mode of action has been assayed against."""
    out: dict[str, list[str]] = {mode: [] for mode in rules.modes()}
    for one in board(book, on):
        mode = one.mode
        if mode is not None and one.species not in out[mode]:
            out[mode].append(one.species)
    return {mode: sorted(found) for mode, found in out.items()}


def untested_here(book: Book, site_id: str, on: dt.date) -> list[tuple[str, str]]:
    """Every product and species pair at a site that nothing has been run on."""
    site = sites.get(book, site_id)
    here = [one.code for one in site.kind.species_here()]
    out: list[tuple[str, str]] = []
    for product in products.for_habitat(book, site.habitat, on=on):
        for code in here:
            if standing(book, product.active, code, on, zone_id=site.zone).assay is None:
                out.append((product.active, code))
    return sorted(set(out))


def species_of(code: str) -> species.Species:
    """The species a finding is about."""
    return species.species(code)
