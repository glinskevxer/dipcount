"""The season to date, and the board's one page.

A season report is not a stack of weekly reports. What the board wants is the
shape: when the first positive pool came in, which week ran hottest, how much
went on the ground, and whether the people and the machines are in a state to
carry on. Those are different questions from "what happened last week" and
they read off different ends of the same records.

The one that catches districts out is the standing section. A licence that
expires in October and a calibration that ran out in August are both
operational facts, and both of them are invisible in every weekly report,
because nothing happened in the week they went out of date.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import clock, species
from dipcount.model.trap import KINDS
from dipcount.report.sheet import Sheet, table
from dipcount.report.use_report import Return, use_return
from dipcount.service import calibration, licensing, trapping, virus
from dipcount.service.virus import Picture
from dipcount.store import inspections, requests, runs, treatments
from dipcount.store.book import Book

FIRST_WEEK = 18
LAST_WEEK = 40


@dataclass(frozen=True)
class Season:
    """One season, gathered."""

    year: int
    on: dt.date
    first: int
    last: int
    weeks: tuple[Picture, ...]
    first_positive: Picture | None
    peak: Picture | None
    filed: Return
    visits: int = 0
    treatments: int = 0
    spray_runs: int = 0
    nights: int = 0
    calls: int = 0
    indices: dict[str, Decimal] = field(default_factory=dict)

    @property
    def positive_weeks(self) -> int:
        """How many weeks had a positive pool in them."""
        return sum(1 for one in self.weeks if one.positive)

    @property
    def highest_level(self) -> str:
        """The furthest up the ladder the season went."""
        order = ["none", "low", "moderate", "high", "emergency"]
        found = [one.level for one in self.weeks]
        return max(found, key=order.index) if found else "none"

    def shape_sheet(self) -> Sheet:
        """The season in figures."""
        rows = [
            ["weeks covered", f"{self.first} to {self.last}"],
            ["larval visits", str(self.visits)],
            ["treatments", str(self.treatments)],
            ["spray runs", str(self.spray_runs)],
            ["nights out", str(self.nights)],
            ["calls taken", str(self.calls)],
            ["weeks with a positive", str(self.positive_weeks)],
            ["highest level", self.highest_level],
            [
                "first positive",
                self.first_positive.label if self.first_positive else "none",
            ],
            ["peak week", self.peak.label if self.peak else "none"],
        ]
        return table(["season", "figure"], rows, title=f"{self.year} season to {self.on}")

    def week_sheet(self) -> Sheet:
        """One line for every week of the season."""
        rows = [
            [
                one.label,
                f"{one.abundance.value:.2f}",
                str(one.rate.pools),
                str(one.rate.positives),
                f"{one.rate.rate:.2f}",
                f"{one.vector_index:.3f}",
                one.level,
            ]
            for one in self.weeks
        ]
        return table(
            ["week", "abundance", "pools", "positive", "rate", "index", "level"],
            rows,
            title=f"{self.year} weekly picture",
        )

    def index_sheet(self) -> Sheet:
        """Mean index for the season, by trap kind."""
        rows = [[kind, f"{value:.2f}"] for kind, value in sorted(self.indices.items())]
        return table(["trap kind", "mean per night"], rows, title="season abundance")

    def sheets(self) -> list[Sheet]:
        """Every table on the report."""
        return [
            self.shape_sheet(),
            self.week_sheet(),
            self.index_sheet(),
            self.filed.totals_sheet(),
        ]

    def render(self) -> str:
        """The whole report as text."""
        return "\n\n".join(one.render() for one in self.sheets())


def _mean_indices(book: Book, year: int, first: int, last: int) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for kind in KINDS:
        weeks = trapping.season(book, year, kind, first=first, last=last)
        counted = [one for one in weeks if one.nights > 0]
        if counted:
            out[kind] = sum((one.value for one in counted), Decimal(0)) / len(counted)
        else:
            out[kind] = Decimal(0)
    return out


def season(
    book: Book,
    year: int,
    *,
    on: dt.date | None = None,
    first: int = FIRST_WEEK,
    last: int = LAST_WEEK,
    virus_name: str = species.WNV,
) -> Season:
    """Gather one season up to a day."""
    when = on if on is not None else dt.date(year, 12, 31)
    weeks = tuple(
        virus.picture(book, year, week, virus_name)
        for week in range(first, min(last, clock.weeks_in_year(year)) + 1)
        if clock.week_start(year, week) <= when
    )
    start, end = dt.date(year, 1, 1), min(when, dt.date(year, 12, 31))
    return Season(
        year=year,
        on=when,
        first=first,
        last=last,
        weeks=weeks,
        first_positive=next((one for one in weeks if one.positive), None),
        peak=max(weeks, key=lambda one: one.vector_index) if weeks else None,
        filed=use_return(book, start, end),
        visits=len(inspections.between(book, start, end)),
        treatments=len(treatments.between(book, start, end)),
        spray_runs=len(runs.between(book, start, end)),
        nights=len(runs.nights(book, start, end)),
        calls=len(requests.between(book, start, end)),
        indices=_mean_indices(book, year, first, last),
    )


@dataclass(frozen=True)
class Board:
    """What is out of date, overdue or unanswered today."""

    on: dt.date
    licences: tuple[licensing.Standing, ...] = field(default_factory=tuple)
    machines: tuple[calibration.Standing, ...] = field(default_factory=tuple)
    late_calls: int = 0
    open_calls: int = 0

    def sheet(self) -> Sheet:
        """The board as one table."""
        rows: list[list[str]] = []
        for one in self.licences:
            rows.append(
                [
                    "licence",
                    one.applicator.name,
                    f"expires {one.applicator.expires_on}",
                    "credits met" if one.renewable else f"{one.hours_short} hours short",
                ],
            )
        for two in self.machines:
            rows.append(
                [
                    "machine",
                    two.machine.model,
                    f"due {two.due_on}" if two.due_on else "never calibrated",
                    f"{two.days_over} days over" if two.days_over else "",
                ],
            )
        rows.append(["calls", "open", str(self.open_calls), f"{self.late_calls} late"])
        return table(["what", "which", "when", "note"], rows, title=f"board, {self.on}")

    def render(self) -> str:
        """The board as text."""
        return self.sheet().render()


def board(book: Book, on: dt.date, *, within: int = 60) -> Board:
    """What needs somebody's attention today."""
    at = clock.moment(f"{on.isoformat()} 12:00")
    waiting = [one for one in requests.unvisited(book) if one.late(at)]
    return Board(
        on=on,
        licences=tuple(licensing.expiring(book, on, days=within)),
        machines=tuple(calibration.due(book, on, within=within)),
        late_calls=len(waiting),
        open_calls=len(requests.open_calls(book)),
    )
