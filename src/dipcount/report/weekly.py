"""The week's surveillance and work, on one sheet.

This is the report the board sees on a Monday and the one the state wants a
copy of. It is deliberately a gathering rather than a calculation: every
figure on it has already been worked out by the service that owns it, and this
module's whole job is to put them next to each other in a way that reads.

The week is the reporting week, Sunday to Saturday, and every section uses the
same one. A summary where the larval figures run Monday to Sunday and the trap
figures run Sunday to Saturday is the kind of thing that survives for years.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import clock, species
from dipcount.model.trap import KINDS
from dipcount.report.sheet import Sheet, table
from dipcount.service import survey, trapping, virus
from dipcount.service.trapping import Index
from dipcount.service.virus import Picture
from dipcount.store import inspections, requests, runs, sites, traps, treatments
from dipcount.store.book import Book


@dataclass(frozen=True)
class Larval:
    """What the dipper found over one week."""

    visits: int = 0
    dry: int = 0
    positive: int = 0
    dips: int = 0
    larvae: int = 0
    pupae: int = 0
    treated: int = 0
    by_habitat: dict[str, int] = field(default_factory=dict)

    @property
    def per_dip(self) -> Decimal:
        """Larvae per dip over the whole week."""
        if not self.dips:
            return Decimal(0)
        return Decimal(self.larvae) / Decimal(self.dips)

    @property
    def wet(self) -> int:
        """How many visits found water."""
        return self.visits - self.dry


@dataclass(frozen=True)
class Work:
    """What went on the ground over one week."""

    treatments: int = 0
    acres: Decimal = Decimal(0)
    structures: Decimal = Decimal(0)
    by_product: dict[str, str] = field(default_factory=dict)
    runs: int = 0
    run_acres: float = 0.0
    nights: int = 0


@dataclass(frozen=True)
class Calls:
    """What the public rang about over one week."""

    taken: int = 0
    answered: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Weekly:
    """One reporting week, gathered."""

    year: int
    week: int
    zone: str | None
    larval: Larval
    indices: tuple[Index, ...]
    picture: Picture
    work: Work
    calls: Calls

    @property
    def label(self) -> str:
        """The week this covers."""
        return f"{self.year}-W{self.week:02d}"

    @property
    def start(self) -> dt.date:
        """The Sunday the week opens on."""
        return clock.week_start(self.year, self.week)

    @property
    def end(self) -> dt.date:
        """The Saturday the week closes on."""
        return clock.week_end(self.year, self.week)

    def larval_sheet(self) -> Sheet:
        """The larval round as a table."""
        rows = [
            ["visits", str(self.larval.visits)],
            ["dry", str(self.larval.dry)],
            ["with water", str(self.larval.wet)],
            ["positive", str(self.larval.positive)],
            ["dips", str(self.larval.dips)],
            ["larvae", str(self.larval.larvae)],
            ["pupae", str(self.larval.pupae)],
            ["larvae per dip", f"{self.larval.per_dip:.2f}"],
            ["treated", str(self.larval.treated)],
        ]
        return table(["larval round", "figure"], rows, title=f"{self.label} larval surveillance")

    def habitat_sheet(self) -> Sheet:
        """Where the positives were, by habitat."""
        rows = [[key, str(count)] for key, count in sorted(self.larval.by_habitat.items())]
        return table(["habitat", "positive visits"], rows)

    def trap_sheet(self) -> Sheet:
        """The trap indices as a table."""
        rows = [
            [
                one.kind,
                str(one.collections),
                str(one.dropped),
                str(one.females),
                str(one.nights),
                f"{one.value:.2f}",
                "yes" if one.over else "",
            ]
            for one in self.indices
        ]
        return table(
            ["trap kind", "jars", "dropped", "females", "nights", "per night", "over"],
            rows,
            title=f"{self.label} adult surveillance",
        )

    def virus_sheet(self) -> Sheet:
        """The virus picture as a table."""
        found = self.picture
        rows = [
            ["abundance", f"{found.abundance.value:.2f} per night"],
            ["pools in the rate", str(found.rate.pools)],
            ["pools held back", str(found.pools_held)],
            ["positive pools", str(found.rate.positives)],
            ["mosquitoes tested", str(found.rate.mosquitoes)],
            ["minimum rate", f"{found.minimum:.2f}"],
            ["estimated rate", f"{found.rate.rate:.2f}"],
            ["vector index", f"{found.vector_index:.3f}"],
            ["level", found.level],
        ]
        return table(["virus", "figure"], rows, title=f"{self.label} {found.virus}")

    def work_sheet(self) -> Sheet:
        """What went on the ground as a table."""
        rows = [
            ["treatments", str(self.work.treatments)],
            ["acres treated", f"{self.work.acres:g}"],
            ["structures treated", f"{self.work.structures:g}"],
            ["spray runs", str(self.work.runs)],
            ["nights out", str(self.work.nights)],
            ["acres fogged", f"{self.work.run_acres:g}"],
        ]
        return table(["work", "figure"], rows, title=f"{self.label} work done")

    def product_sheet(self) -> Sheet:
        """What was used, by product."""
        rows = [[name, amount] for name, amount in sorted(self.work.by_product.items())]
        return table(["product", "used"], rows)

    def call_sheet(self) -> Sheet:
        """What the public rang about."""
        rows = [[kind, str(count)] for kind, count in sorted(self.calls.by_kind.items())]
        return table(["call", "taken"], rows, title=f"{self.label} calls")

    def sheets(self) -> list[Sheet]:
        """Every table on the report, in the order they print."""
        return [
            self.larval_sheet(),
            self.habitat_sheet(),
            self.trap_sheet(),
            self.virus_sheet(),
            self.work_sheet(),
            self.product_sheet(),
            self.call_sheet(),
        ]

    def render(self) -> str:
        """The whole report as text."""
        head = f"{self.label}  {self.start} to {self.end}"
        if self.zone is not None:
            head = f"{head}  zone {self.zone}"
        return "\n\n".join([head, *[one.render() for one in self.sheets()]])


def _larval(book: Book, year: int, week: int, zone_id: str | None) -> Larval:
    wanted = {one.id: one for one in sites.all_sites(book, zone_id=zone_id)}
    found = [one for one in inspections.in_week(book, year, week) if one.site in wanted]
    by_habitat: dict[str, int] = {}
    treated = 0
    for one in found:
        site = wanted[one.site]
        if one.positive:
            by_habitat[site.habitat] = by_habitat.get(site.habitat, 0) + 1
        if survey.assess(site, one).treatable:
            treated += 1
    return Larval(
        visits=len(found),
        dry=sum(1 for one in found if not one.water),
        positive=sum(1 for one in found if one.positive),
        dips=sum(one.dips for one in found),
        larvae=sum(one.larvae for one in found),
        pupae=sum(one.pupae for one in found),
        treated=treated,
        by_habitat=by_habitat,
    )


def _work(book: Book, year: int, week: int, zone_id: str | None) -> Work:
    wanted = {one.id for one in sites.all_sites(book, zone_id=zone_id)}
    made = [one for one in treatments.in_week(book, year, week) if one.site in wanted]
    acres = Decimal(0)
    structures = Decimal(0)
    by_product: dict[str, str] = {}
    totals: dict[str, tuple[Decimal, str]] = {}
    for one in made:
        if one.extent.unit == "acre":
            acres += one.extent.amount
        else:
            structures += one.extent.amount
        held, unit = totals.get(one.product, (Decimal(0), one.amount.unit))
        totals[one.product] = (held + one.amount.to(unit).amount, unit)
    for product, (amount, unit) in totals.items():
        by_product[product] = f"{amount} {unit}"
    made_runs = runs.in_week(book, year, week)
    return Work(
        treatments=len(made),
        acres=acres,
        structures=structures,
        by_product=by_product,
        runs=len(made_runs),
        run_acres=sum(one.acres for one in made_runs),
        nights=len({one.on for one in made_runs}),
    )


def _calls(book: Book, year: int, week: int, zone_id: str | None) -> Calls:
    found = [
        one for one in requests.in_week(book, year, week) if zone_id is None or one.zone == zone_id
    ]
    by_kind: dict[str, int] = {}
    for one in found:
        by_kind[one.kind] = by_kind.get(one.kind, 0) + 1
    return Calls(
        taken=len(found),
        answered=sum(1 for one in found if one.visited),
        by_kind=by_kind,
    )


def weekly(
    book: Book,
    year: int,
    week: int,
    *,
    zone_id: str | None = None,
    virus_name: str = species.WNV,
) -> Weekly:
    """Gather one reporting week."""
    indices = tuple(trapping.week_index(book, year, week, kind, zone_id=zone_id) for kind in KINDS)
    return Weekly(
        year=year,
        week=week,
        zone=zone_id,
        larval=_larval(book, year, week, zone_id),
        indices=indices,
        picture=virus.picture(book, year, week, virus_name, zone_id=zone_id),
        work=_work(book, year, week, zone_id),
        calls=_calls(book, year, week, zone_id),
    )


def busiest_habitat(found: Weekly) -> str | None:
    """The habitat with the most positive visits, if there were any."""
    if not found.larval.by_habitat:
        return None
    return max(found.larval.by_habitat.items(), key=lambda pair: (pair[1], pair[0]))[0]


def trap_nights(found: Weekly) -> Decimal:
    """Every trap night in the week, across all kinds."""
    return sum((one.nights for one in found.indices), Decimal(0))


def collections(book: Book, year: int, week: int) -> int:
    """How many jars came in over one reporting week."""
    return len(traps.in_week(book, year, week))
