"""The answer clock on a call, and how the season moves it.

A call has an answer time that comes off its kind. That much is a lookup. What
makes it worth a service is that the district's own response level moves two
of those times: in a high or emergency week a dead bird is answered in twelve
hours rather than twenty four, and a spray concern with it, because both of
them feed decisions being made that night. The other kinds do not move,
because finding standing water does not get faster when the season is bad.

So the same call, on the same day, at the same address, is late in one season
and comfortable in another. Anything reporting on response times has to read
the level for the week the call was taken in, not the level today.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from dipcount import clock, rules, species
from dipcount.model.request import DEAD_BIRD, SPRAY, Request
from dipcount.service import virus
from dipcount.store import audit, requests
from dipcount.store.book import Book

FAST_KINDS = (DEAD_BIRD, SPRAY)
"""The kinds whose clock a busy virus week shortens."""


@dataclass(frozen=True)
class Standing:
    """Where one call stands against its clock."""

    request: Request
    now: dt.datetime
    hours: int
    level: str = "none"

    @property
    def escalated(self) -> bool:
        """Whether the season shortened this call's clock."""
        return self.hours < self.request.hours

    @property
    def due_at(self) -> dt.datetime:
        """When the answer is due, after any escalation."""
        return self.request.taken_at + dt.timedelta(hours=self.hours)

    @property
    def late(self) -> bool:
        """Whether the answer time has run out without a visit."""
        if self.request.visited_at is not None:
            return self.request.visited_at > self.due_at
        return self.now > self.due_at

    @property
    def hours_left(self) -> Decimal:
        """How long is left, which goes negative when it is late."""
        seconds = clock.elapsed(self.now, self.due_at).total_seconds()
        return Decimal(str(round(seconds / 3600, 2)))

    def line(self) -> str:
        """One line for a call sheet."""
        tail = "late" if self.late else f"{self.hours_left} hours left"
        moved = f" (cut from {self.request.hours} by {self.level})" if self.escalated else ""
        return f"{self.request.id}  {self.request.kind}  {tail}{moved}"


def _level_for(book: Book, call: Request) -> str:
    year, week = clock.epi_week(clock.in_zone(call.taken_at).date())
    return virus.picture(book, year, week, species.WNV, zone_id=call.zone).level


def hours_for(book: Book, call: Request) -> tuple[int, str]:
    """How long this call really has, and the level that decided it."""
    level = _level_for(book, call)
    if call.kind in FAST_KINDS and level in rules.ESCALATED_LEVELS:
        return max(call.hours // 2, 1), level
    return call.hours, level


def standing(book: Book, request_id: str, now: dt.datetime) -> Standing:
    """Where one call stands against its clock."""
    call = requests.get(book, request_id)
    hours, level = hours_for(book, call)
    return Standing(request=call, now=now, hours=hours, level=level)


def take(
    book: Book,
    actor: str,
    kind: str,
    zone_id: str,
    taken_at: dt.datetime,
    address: str,
    *,
    caller: str = "",
    phone: str = "",
    detail: str = "",
) -> Request:
    """Write a call down and leave a line on the trail."""
    with book.writing():
        made = requests.take(
            book,
            kind,
            zone_id,
            taken_at,
            address,
            caller=caller,
            phone=phone,
            detail=detail,
        )
        audit.record(book, actor, "took call", made.id, f"{kind} at {address}", at=taken_at)
    return made


def answer(
    book: Book,
    actor: str,
    request_id: str,
    visited_at: dt.datetime,
    *,
    site_id: str | None = None,
) -> Standing:
    """Record a visit and say whether it was inside the clock."""
    with book.writing():
        made = requests.visit(book, request_id, visited_at, site_id=site_id)
        hours, level = hours_for(book, made)
        where = Standing(request=made, now=visited_at, hours=hours, level=level)
        audit.record(
            book,
            actor,
            "answered call",
            made.id,
            f"{'late' if where.late else 'in time'}, {made.answered_in()} hours",
            at=visited_at,
        )
    return where


def finish(
    book: Book,
    actor: str,
    request_id: str,
    closed_at: dt.datetime,
    outcome: str,
) -> Request:
    """Close a call with what came of it."""
    with book.writing():
        made = requests.close(book, request_id, closed_at, outcome)
        audit.record(book, actor, "closed call", made.id, outcome, at=closed_at)
    return made


def waiting(book: Book, now: dt.datetime, *, zone_id: str | None = None) -> list[Standing]:
    """Every unanswered call, least time left first."""
    out = [standing(book, one.id, now) for one in requests.unvisited(book, zone_id=zone_id)]
    return sorted(out, key=lambda one: (one.hours_left, one.request.id))


def overdue(book: Book, now: dt.datetime, *, zone_id: str | None = None) -> list[Standing]:
    """Every unanswered call whose clock has run out."""
    return [one for one in waiting(book, now, zone_id=zone_id) if one.late]


@dataclass(frozen=True)
class Performance:
    """How the district answered its calls over a window."""

    start: dt.date
    end: dt.date
    taken: int
    answered: int
    on_time: int
    median_hours: Decimal | None = None

    @property
    def share_on_time(self) -> Decimal:
        """What share of the answered calls were inside the clock."""
        if not self.answered:
            return Decimal(0)
        return Decimal(self.on_time) / Decimal(self.answered)

    def line(self) -> str:
        """One line for a board report."""
        middle = "no answers" if self.median_hours is None else f"median {self.median_hours} h"
        return (
            f"{self.start} to {self.end}  {self.taken} calls"
            f"  {self.answered} answered  {self.share_on_time:.0%} in time  {middle}"
        )


def performance(book: Book, start: dt.date, end: dt.date) -> Performance:
    """How the calls taken over a window were answered."""
    taken = requests.between(book, start, end)
    answered = [one for one in taken if one.visited_at is not None]
    on_time = 0
    hours: list[Decimal] = []
    for call in answered:
        wanted, level = hours_for(book, call)
        where = Standing(
            request=call,
            now=call.visited_at or call.taken_at,
            hours=wanted,
            level=level,
        )
        if not where.late:
            on_time += 1
        took = call.answered_in()
        if took is not None:
            hours.append(took)
    return Performance(
        start=start,
        end=end,
        taken=len(taken),
        answered=len(answered),
        on_time=on_time,
        median_hours=Decimal(str(median(hours))) if hours else None,
    )
