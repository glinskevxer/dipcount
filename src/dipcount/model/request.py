"""What the public rings up about, and how long the district has to answer.

Every call is a service request whether or not anything comes of it, because
the count of calls is the only measure the district has of what the season
feels like from the outside. A quiet week with forty biting complaints is not
a quiet week.

The clock is the part with teeth. Each kind of call has its own answer time,
and the times are not a ranking of how upset the caller is. A dead bird is
answered fastest because the carcass decays and the laboratory cannot test a
bird that has sat in the sun. A spray concern is answered fast because the run
it is about happens tonight. A biting complaint gets three days because
answering it means finding water, and water does not move.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from dipcount import clock, ids
from dipcount.errors import UsageError
from dipcount.rows import Row

BITING: Final = "biting"
WATER: Final = "standing water"
DEAD_BIRD: Final = "dead bird"
SPRAY: Final = "spray concern"
TYRES: Final = "tyre pile"
OTHER: Final = "other"

_HOURS: Final[dict[str, int]] = {
    DEAD_BIRD: 24,
    SPRAY: 24,
    WATER: 48,
    TYRES: 72,
    BITING: 72,
    OTHER: 120,
}

_WHY: Final[dict[str, str]] = {
    DEAD_BIRD: "the carcass decays and the laboratory cannot test what has sat in the sun",
    SPRAY: "the run it is about is tonight",
    WATER: "water that is producing now is producing every four days",
    TYRES: "a pile has been there for years and will be there next week",
    BITING: "answering it means finding water, and water does not move",
    OTHER: "nothing about it is urgent until somebody has read it",
}


def kinds() -> list[str]:
    """Every kind of call, in the order they are answered."""
    return sorted(_HOURS, key=lambda one: (_HOURS[one], one))


def answer_hours(kind: str) -> int:
    """How long the district has to answer one kind of call."""
    try:
        return _HOURS[kind]
    except KeyError as exc:
        raise UsageError(f"{kind} is not a kind of call: try {', '.join(_HOURS)}") from exc


def why(kind: str) -> str:
    """Why that kind of call is answered in that time."""
    answer_hours(kind)
    return _WHY[kind]


@dataclass(frozen=True)
class Request:
    """One call from the public."""

    id: str
    kind: str
    zone: str
    taken_at: dt.datetime
    address: str
    caller: str = ""
    phone: str = ""
    detail: str = ""
    assigned_to: str | None = None
    visited_at: dt.datetime | None = None
    site: str | None = None
    closed_at: dt.datetime | None = None
    outcome: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("request", self.id)
        ids.require("zone", self.zone)
        answer_hours(self.kind)
        if not self.address.strip():
            raise UsageError("a call needs somewhere to go to")
        if self.taken_at.tzinfo is None:
            raise UsageError("a call needs a moment with a zone")
        if self.assigned_to is not None:
            ids.require("applicator", self.assigned_to)
        if self.site is not None:
            ids.require("site", self.site)
        for moment in (self.visited_at, self.closed_at):
            if moment is not None and moment.tzinfo is None:
                raise UsageError("a call needs moments with zones")
        if self.visited_at is not None and self.visited_at < self.taken_at:
            raise UsageError("a call cannot be visited before it came in")
        if self.closed_at is not None and self.closed_at < self.taken_at:
            raise UsageError("a call cannot be closed before it came in")
        if self.closed_at is not None and not self.outcome.strip():
            raise UsageError("a closed call needs an outcome")

    @property
    def hours(self) -> int:
        """How long the district has to answer this call."""
        return answer_hours(self.kind)

    @property
    def due_at(self) -> dt.datetime:
        """When the answer is due."""
        return self.taken_at + dt.timedelta(hours=self.hours)

    @property
    def open(self) -> bool:
        """Whether the call is still open."""
        return self.closed_at is None

    @property
    def visited(self) -> bool:
        """Whether somebody has been out to it."""
        return self.visited_at is not None

    def answered_in(self) -> Decimal | None:
        """How long the visit took, in hours, if there has been one."""
        if self.visited_at is None:
            return None
        seconds = clock.elapsed(self.taken_at, self.visited_at).total_seconds()
        return Decimal(str(round(seconds / 3600, 2)))

    def late(self, now: dt.datetime) -> bool:
        """Whether the answer time has run out without a visit.

        A call visited after its time is late for good; the clock does not
        reset when somebody finally gets there.
        """
        if self.visited_at is not None:
            return self.visited_at > self.due_at
        return now > self.due_at

    def hours_left(self, now: dt.datetime) -> Decimal:
        """How long is left to answer, which goes negative when it is late."""
        seconds = clock.elapsed(now, self.due_at).total_seconds()
        return Decimal(str(round(seconds / 3600, 2)))

    def line(self) -> str:
        """One line for a call sheet."""
        state = "closed" if not self.open else ("visited" if self.visited else "open")
        return (
            f"{self.id}  {self.kind}  {self.address}"
            f"  taken {clock.stamp(self.taken_at)}  due {clock.stamp(self.due_at)}  {state}"
        )

    @classmethod
    def from_row(cls, row: Row) -> Request:
        """Read a call off a database row."""

        def moment(name: str) -> dt.datetime | None:
            """One of the optional moments, or nothing when it is empty."""
            value = row[name]
            return None if value is None else dt.datetime.fromisoformat(str(value))

        assigned = row["assigned_to"]
        site = row["site"]
        return cls(
            id=str(row["id"]),
            kind=str(row["kind"]),
            zone=str(row["zone"]),
            taken_at=dt.datetime.fromisoformat(str(row["taken_at"])),
            address=str(row["address"]),
            caller=str(row["caller"]),
            phone=str(row["phone"]),
            detail=str(row["detail"]),
            assigned_to=None if assigned is None else str(assigned),
            visited_at=moment("visited_at"),
            site=None if site is None else str(site),
            closed_at=moment("closed_at"),
            outcome=str(row["outcome"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this call would be written as."""
        return {
            "id": self.id,
            "kind": self.kind,
            "zone": self.zone,
            "taken_at": clock.to_utc(self.taken_at).isoformat(),
            "caller": self.caller,
            "phone": self.phone,
            "address": self.address,
            "detail": self.detail,
            "assigned_to": self.assigned_to,
            "visited_at": None
            if self.visited_at is None
            else clock.to_utc(
                self.visited_at,
            ).isoformat(),
            "site": self.site,
            "closed_at": None
            if self.closed_at is None
            else clock.to_utc(
                self.closed_at,
            ).isoformat(),
            "outcome": self.outcome,
            "note": self.note,
        }
