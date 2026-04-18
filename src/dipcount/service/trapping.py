"""Turning jars of mosquitoes into an index somebody can act on.

Females per trap night sounds like one number and is really three decisions.
Which collections belong in it, because a trap that did not run is not a night
of nothing. Which insects belong in it, because males do not bite. And what it
is compared against, because fifty a night off a light trap is an ordinary
July and ten a night off a gravid trap is a problem.

The baseline is the part that goes wrong quietly. It is the mean of the same
reporting week in the seasons before, over the same kind of trap, and a
district in its first season has no baseline at all. Reporting a ratio against
a baseline of nothing produces either a division by zero or a false calm, so
the absence is carried in the result rather than papered over.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import clock, rules, species
from dipcount.model.trap import Catch, Collection, Trap
from dipcount.store import audit, traps
from dipcount.store.book import Book


@dataclass(frozen=True)
class Index:
    """Females per trap night over a set of collections."""

    year: int
    week: int
    kind: str
    females: int
    nights: Decimal
    collections: int
    dropped: int = 0
    species: str = ""

    @property
    def reasons(self) -> tuple[str, ...]:
        """The clauses that decided what this index counts."""
        out = ["adult.threshold"]
        if self.dropped:
            out.append("adult.broken")
        return tuple(out)

    @property
    def value(self) -> Decimal:
        """The index itself, which is nothing when nothing ran."""
        if self.nights == 0:
            return Decimal(0)
        return self.females / self.nights

    @property
    def label(self) -> str:
        """The week this index covers."""
        return f"{self.year}-W{self.week:02d}"

    @property
    def threshold(self) -> Decimal:
        """The figure this kind of trap is measured against."""
        return rules.adult_threshold(self.kind)

    @property
    def over(self) -> bool:
        """Whether the index has reached the figure for its trap kind."""
        return self.nights > 0 and self.value >= self.threshold

    def line(self) -> str:
        """One line for a weekly sheet."""
        what = self.species or "all"
        return (
            f"{self.label}  {self.kind}  {what}  {self.value:.2f}/night"
            f"  ({self.females} in {self.nights} nights, {self.dropped} dropped)"
        )


@dataclass(frozen=True)
class Trend:
    """One week's index against the baseline for that week."""

    index: Index
    baseline: Decimal | None
    seasons: int = 0
    years: tuple[int, ...] = field(default_factory=tuple)

    @property
    def reasons(self) -> tuple[str, ...]:
        """The clauses this trend rests on."""
        return (*self.index.reasons, "adult.baseline")

    @property
    def has_baseline(self) -> bool:
        """Whether there is anything to compare against."""
        return self.baseline is not None and self.baseline > 0

    @property
    def ratio(self) -> Decimal | None:
        """How many times the baseline this week ran."""
        if self.baseline is None or self.baseline == 0:
            return None
        return self.index.value / self.baseline

    @property
    def elevated(self) -> bool:
        """Whether the week is far enough over the baseline to report."""
        ratio = self.ratio
        return ratio is not None and ratio >= rules.ELEVATED

    def line(self) -> str:
        """One line for a weekly sheet."""
        if not self.has_baseline:
            return f"{self.index.line()}  no baseline"
        ratio = self.ratio
        assert ratio is not None
        tail = "elevated" if self.elevated else "ordinary"
        return f"{self.index.line()}  {ratio:.2f} times the usual, {tail}"


def _counted(collections: list[Collection]) -> tuple[list[Collection], int]:
    kept = [one for one in collections if one.worked]
    return kept, len(collections) - len(kept)


def index_over(
    collections: list[Collection],
    year: int,
    week: int,
    kind: str,
    *,
    code: str = "",
) -> Index:
    """Work out the index over a set of collections that are already chosen."""
    kept, dropped = _counted(collections)
    females = sum(one.females_of(code) if code else one.females for one in kept)
    nights = sum((one.nights for one in kept), Decimal(0))
    return Index(
        year=year,
        week=week,
        kind=kind,
        females=females,
        nights=nights,
        collections=len(kept),
        dropped=dropped,
        species=code,
    )


def _traps_of(book: Book, kind: str, zone_id: str | None) -> dict[str, Trap]:
    return {one.id: one for one in traps.all_traps(book, zone_id=zone_id, kind=kind)}


def week_index(
    book: Book,
    year: int,
    week: int,
    kind: str,
    *,
    zone_id: str | None = None,
    code: str = "",
) -> Index:
    """The index for one reporting week over one kind of trap."""
    wanted = _traps_of(book, kind, zone_id)
    found = [one for one in traps.in_week(book, year, week) if one.trap in wanted]
    return index_over(found, year, week, kind, code=code)


def baseline(
    book: Book,
    year: int,
    week: int,
    kind: str,
    *,
    zone_id: str | None = None,
    code: str = "",
    seasons: int = rules.BASELINE_SEASONS,
) -> tuple[Decimal | None, tuple[int, ...]]:
    """The mean index for this week in the seasons before, and which ones."""
    values: list[Decimal] = []
    years: list[int] = []
    for back in range(1, seasons + 1):
        earlier = year - back
        if week > clock.weeks_in_year(earlier):
            continue
        found = week_index(book, earlier, week, kind, zone_id=zone_id, code=code)
        if found.collections == 0:
            continue
        values.append(found.value)
        years.append(earlier)
    if not values:
        return None, ()
    return sum(values, Decimal(0)) / len(values), tuple(sorted(years))


def trend(
    book: Book,
    year: int,
    week: int,
    kind: str,
    *,
    zone_id: str | None = None,
    code: str = "",
    seasons: int = rules.BASELINE_SEASONS,
) -> Trend:
    """This week's index set against the seasons before it."""
    now = week_index(book, year, week, kind, zone_id=zone_id, code=code)
    mean, years = baseline(
        book,
        year,
        week,
        kind,
        zone_id=zone_id,
        code=code,
        seasons=seasons,
    )
    return Trend(index=now, baseline=mean, seasons=len(years), years=years)


def season(
    book: Book,
    year: int,
    kind: str,
    *,
    first: int = 18,
    last: int = 40,
    zone_id: str | None = None,
    code: str = "",
) -> list[Index]:
    """One index for every week of a season."""
    weeks = min(last, clock.weeks_in_year(year))
    return [
        week_index(book, year, week, kind, zone_id=zone_id, code=code)
        for week in range(first, weeks + 1)
    ]


def vector_index(
    book: Book,
    year: int,
    week: int,
    virus: str,
    *,
    kind: str = "gravid",
    zone_id: str | None = None,
) -> Index:
    """The index over only the species that carry a named virus."""
    wanted = _traps_of(book, kind, zone_id)
    found = [one for one in traps.in_week(book, year, week) if one.trap in wanted]
    kept, dropped = _counted(found)
    codes = [one.code for one in species.vectors_of(virus)]
    females = sum(sum(one.females_of(code) for code in codes) for one in kept)
    nights = sum((one.nights for one in kept), Decimal(0))
    return Index(
        year=year,
        week=week,
        kind=kind,
        females=females,
        nights=nights,
        collections=len(kept),
        dropped=dropped,
        species=virus,
    )


def collect(
    book: Book,
    actor: str,
    trap_id: str,
    set_at: dt.datetime,
    pulled_at: dt.datetime,
    *,
    worked: bool = True,
    catches: tuple[Catch, ...] = (),
    note: str = "",
) -> Collection:
    """Write a collection and leave a line on the trail.

    The trail line carries the index for that jar rather than the raw count,
    because the count on its own says nothing until it is divided by the
    nights the trap was out.
    """
    trap = traps.resolve(book, trap_id)
    with book.writing():
        made = traps.record(
            book,
            trap.id,
            set_at,
            pulled_at,
            actor,
            worked=worked,
            catches=catches,
            note=note,
        )
        detail = (
            f"{made.id}: did not run"
            if not made.worked
            else f"{made.id}: {made.females} females in {made.nights} nights"
        )
        audit.record(book, actor, "collected", trap.id, detail, at=pulled_at)
    return made


def due(book: Book, on: dt.date, *, every: int = 7, zone_id: str | None = None) -> list[Trap]:
    """Every open trap that has not been run in the last ``every`` days."""
    out: list[Trap] = []
    for trap in traps.open_on(book, on, zone_id=zone_id):
        last = traps.last_for_trap(book, trap.id)
        if last is None or (on - last.on).days >= every:
            out.append(trap)
    return out
