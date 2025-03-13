"""Reading an inspection and saying what it means.

:func:`assess` is the whole larval decision in one place and it holds no
database. Give it a site and an inspection and it says what the district
should do next, which clauses it used to get there, and when the site is due
again. Everything that writes calls it; the tests can call it with a made up
inspection and no book at all.

The order the clauses run in is the part worth reading twice. A brood that is
mostly pupae is past treating whatever the count says, but only if the count
was going to be worth treating in the first place. Two pupae and two larvae is
half pupae and it is not a brood; the rule has nothing to say about it, and
saying "past treating" there would take a site off the round for no reason.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import rules
from dipcount.model.audit import Entry
from dipcount.model.inspection import Inspection, Tally
from dipcount.model.site import Site
from dipcount.store import audit, inspections, sites
from dipcount.store.book import Book

TREAT = "treat"
URGENT = "treat today"
PAST = "past treating"
WATCH = "watch"
NOTHING = "nothing"
DRY = "dry"


@dataclass(frozen=True)
class Finding:
    """What one inspection means, and which clauses said so."""

    site: str
    inspection: str
    verdict: str
    per_dip: Decimal
    threshold: Decimal
    next_visit: dt.date
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def treatable(self) -> bool:
        """Whether a larvicide should go on this site."""
        return self.verdict in (TREAT, URGENT)

    @property
    def urgent(self) -> bool:
        """Whether it has to go on within the day."""
        return self.verdict == URGENT

    def why(self) -> list[str]:
        """The sentences from the rule book that produced this verdict."""
        return [rules.clause(name).text for name in self.reasons]

    def line(self) -> str:
        """One line for a round sheet."""
        return (
            f"{self.site}  {self.inspection}  {self.verdict}"
            f"  {self.per_dip:.2f}/dip against {self.threshold:.2f}"
            f"  next {self.next_visit.isoformat()}"
        )


def assess(site: Site, inspection: Inspection) -> Finding:
    """Say what an inspection means for the site it was made at."""
    on = inspection.on
    interval = site.kind.interval_days
    vector = rules.carries_a_vector(inspection.species_seen())
    figure = rules.threshold(site.habitat, vector)
    reasons: list[str] = []

    if not inspection.water:
        return Finding(
            site.id,
            inspection.id,
            DRY,
            Decimal(0),
            figure,
            on + dt.timedelta(days=interval),
            ("larval.dry",),
        )

    if vector:
        reasons.append("larval.vector")

    immatures = Decimal(inspection.larvae + inspection.pupae)
    per_immature_dip = immatures / Decimal(inspection.dips) if inspection.dips else Decimal(0)

    if per_immature_dip >= figure and inspection.pupal_share >= rules.PUPAL_STOP:
        return Finding(
            site.id,
            inspection.id,
            PAST,
            inspection.per_dip,
            figure,
            on + dt.timedelta(days=3),
            (*reasons, "larval.pupal"),
        )

    if inspection.per_dip >= figure:
        reasons.append("larval.threshold")
        verdict = TREAT
        if inspection.late_share >= rules.LATE_URGENT:
            reasons.append("larval.late")
            verdict = URGENT
        return Finding(
            site.id,
            inspection.id,
            verdict,
            inspection.per_dip,
            figure,
            on + dt.timedelta(days=interval),
            tuple(reasons),
        )

    if inspection.rafts and not inspection.larvae:
        reasons.append("larval.raft")
        return Finding(
            site.id,
            inspection.id,
            WATCH,
            inspection.per_dip,
            figure,
            on + dt.timedelta(days=rules.RAFT_INTERVAL),
            tuple(reasons),
        )

    return Finding(
        site.id,
        inspection.id,
        NOTHING,
        inspection.per_dip,
        figure,
        on + dt.timedelta(days=interval),
        tuple(reasons),
    )


def inspect(
    book: Book,
    actor: str,
    site_id: str,
    at: dt.datetime,
    *,
    water: bool = True,
    dips: int = 0,
    tallies: tuple[Tally, ...] = (),
    note: str = "",
) -> tuple[Inspection, Finding]:
    """Write an inspection, judge it, and leave a line on the trail."""
    site = sites.get(book, site_id)
    with book.writing():
        made = inspections.record(
            book,
            site_id,
            at,
            actor,
            water=water,
            dips=dips,
            tallies=tallies,
            note=note,
        )
        found = assess(site, made)
        audit.record(
            book,
            actor,
            "inspected",
            site_id,
            f"{made.id}: {found.verdict}, {found.per_dip:.2f}/dip",
            at=at,
        )
    return made, found


def judge(book: Book, inspection_id: str) -> Finding:
    """Read an inspection back out of the book and judge it again."""
    made = inspections.get(book, inspection_id)
    return assess(sites.get(book, made.site), made)


def due(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[tuple[Site, dt.date]]:
    """Every open site due for a visit, most overdue first.

    A site nobody has ever visited is due from the day it was listed, which
    puts a newly listed site at the front of the round rather than nowhere.
    """
    out: list[tuple[Site, dt.date]] = []
    for site in sites.open_on(book, on, zone_id=zone_id):
        last = inspections.last_seen(book, site.id, on=on)
        when = assess(site, last).next_visit if last is not None else site.listed_on
        if when <= on:
            out.append((site, when))
    return sorted(out, key=lambda pair: (pair[1], pair[0].id))


def history(book: Book, site_id: str, *, since: dt.date | None = None) -> list[Finding]:
    """Every inspection of a site judged again, oldest first."""
    site = sites.get(book, site_id)
    return [assess(site, one) for one in inspections.for_site(book, site_id, since=since)]


def trail_for(book: Book, site_id: str) -> list[Entry]:
    """The audit lines about one site's inspections."""
    return [one for one in audit.about(book, site_id) if one.action == "inspected"]
