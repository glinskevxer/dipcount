"""The virus picture for a reporting week.

Three numbers go into the answer and each of them is chosen rather than found.
Abundance is females per trap night off the traps that catch fed females.
Infection rate is estimated over the pools of species that carry the virus, so
a hundred negative pools of a species that has never carried anything does not
push the rate towards zero. And the product of the two is the vector index,
which is what the response ladder reads, because either half on its own
describes a different season.

Everything is keyed on the week the jar was pulled, not the week the vial
reached the laboratory. Couriers run on different days in different counties
and a state adding six districts together needs them on the same clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import estimate, rules, species
from dipcount.model.pool import Pool
from dipcount.service.trapping import Index, week_index
from dipcount.store import pools, traps
from dipcount.store.book import Book


@dataclass(frozen=True)
class Picture:
    """What one virus was doing in one reporting week."""

    year: int
    week: int
    virus: str
    kind: str
    abundance: Index
    rate: estimate.Estimate
    minimum: Decimal
    vector_index: Decimal
    level: str
    pools_held: int = 0
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def label(self) -> str:
        """The week this picture covers."""
        return f"{self.year}-W{self.week:02d}"

    @property
    def positive(self) -> bool:
        """Whether anything came back positive."""
        return self.rate.positives > 0

    def line(self) -> str:
        """One line for a weekly sheet."""
        return (
            f"{self.label}  {self.virus}  abundance {self.abundance.value:.2f}"
            f"  rate {self.rate.rate:.2f}  index {self.vector_index:.3f}  {self.level}"
        )


def pools_in_week(book: Book, year: int, week: int) -> list[Pool]:
    """Every pool made out of a jar pulled in one reporting week."""
    out: list[Pool] = []
    for collection in traps.in_week(book, year, week):
        out.extend(pools.for_collection(book, collection.id))
    return sorted(out, key=lambda one: one.id)


def _shape(
    book: Book,
    year: int,
    week: int,
    virus: str,
    zone_id: str | None,
) -> tuple[list[int], list[bool], int]:
    """The pool sizes and outcomes a rate rests on, and how many were held.

    A pool is held back when the species in it does not carry the virus, or
    when the laboratory has not read it. Both are counted, so a report can say
    the rate rests on fewer pools than were sent.
    """
    wanted = {one.id for one in traps.all_traps(book, zone_id=zone_id)} if zone_id else None
    sizes: list[int] = []
    hits: list[bool] = []
    held = 0
    for pool in pools_in_week(book, year, week):
        if wanted is not None:
            collection = traps.get_collection(book, pool.collection)
            if collection.trap not in wanted:
                continue
        if not pool.could_carry(virus) or not pool.counts_for(virus):
            held += 1
            continue
        sizes.append(pool.size)
        hits.append(pool.is_positive(virus))
    return sizes, hits, held


def rate_for(
    book: Book,
    year: int,
    week: int,
    virus: str,
    *,
    zone_id: str | None = None,
) -> tuple[estimate.Estimate, int]:
    """The infection rate for a week, and how many pools were held back."""
    sizes, hits, held = _shape(book, year, week, virus, zone_id)
    return estimate.estimate(sizes, hits), held


def picture(
    book: Book,
    year: int,
    week: int,
    virus: str,
    *,
    kind: str = "gravid",
    zone_id: str | None = None,
) -> Picture:
    """Abundance, infection rate and the level they put the district on."""
    codes = [one.code for one in species.vectors_of(virus)]
    abundance = _vector_abundance(book, year, week, kind, codes, zone_id)
    sizes, hits, held = _shape(book, year, week, virus, zone_id)
    rate = estimate.estimate(sizes, hits)
    minimum = estimate.minimum_infection_rate(sizes, hits)
    index = estimate.vector_index(abundance.value, rate.rate)
    reasons = ["virus.vector", "virus.week", "virus.ladder"]
    if held:
        reasons.append("virus.pools")
    return Picture(
        year=year,
        week=week,
        virus=virus,
        kind=kind,
        abundance=abundance,
        rate=rate,
        minimum=minimum,
        vector_index=index,
        level=rules.response_level(index),
        pools_held=held,
        reasons=tuple(reasons),
    )


def _vector_abundance(
    book: Book,
    year: int,
    week: int,
    kind: str,
    codes: list[str],
    zone_id: str | None,
) -> Index:
    parts = [week_index(book, year, week, kind, zone_id=zone_id, code=code) for code in codes]
    if not parts:
        return week_index(book, year, week, kind, zone_id=zone_id)
    females = sum(one.females for one in parts)
    return Index(
        year=year,
        week=week,
        kind=kind,
        females=females,
        nights=parts[0].nights,
        collections=parts[0].collections,
        dropped=parts[0].dropped,
        species="vectors",
    )


def season(
    book: Book,
    year: int,
    virus: str,
    *,
    first: int = 22,
    last: int = 40,
    kind: str = "gravid",
    zone_id: str | None = None,
) -> list[Picture]:
    """One picture for every week of a season."""
    return [
        picture(book, year, week, virus, kind=kind, zone_id=zone_id)
        for week in range(first, last + 1)
    ]


def first_positive(book: Book, year: int, virus: str, *, last: int = 45) -> Picture | None:
    """The earliest week of a season anything came back positive."""
    for week in range(1, last + 1):
        found = picture(book, year, week, virus)
        if found.positive:
            return found
    return None


def peak(book: Book, year: int, virus: str, *, first: int = 22, last: int = 40) -> Picture | None:
    """The week of a season with the highest vector index."""
    weeks = season(book, year, virus, first=first, last=last)
    ranked = [one for one in weeks if one.vector_index > 0]
    if not ranked:
        return None
    return max(ranked, key=lambda one: one.vector_index)
