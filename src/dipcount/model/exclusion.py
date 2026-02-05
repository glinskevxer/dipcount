"""The register of places the district does not spray over.

Every district keeps one and every district keeps it differently, because the
entries come from different laws. A registered apiary is on it because the
state registers beekeepers and requires notice. An organic farm is on it
because a drift event costs the grower a certification worth more than the
season. A person on the pesticide sensitivity register is on it because they
asked to be. A fish hatchery is on it because a pyrethroid in the raceway
kills the stock outright.

Those are not the same rule and the difference is the whole of this module.
Some entries want notice: tell them the night before and the work goes ahead.
Others are absolute: no amount of notice makes it acceptable to fog over a
raceway, and an entry like that takes the block off the run rather than
delaying it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from dipcount import ids
from dipcount.errors import UsageError
from dipcount.rows import Row

APIARY: Final = "apiary"
ORGANIC: Final = "organic farm"
SENSITIVE: Final = "sensitive person"
AQUACULTURE: Final = "aquaculture"
WATER: Final = "open water"


@dataclass(frozen=True)
class Sort:
    """One kind of entry, and what being on the register means for it."""

    key: str
    absolute: bool
    notice_hours: int
    buffer_ft: int
    why: str


SORTS: Final[dict[str, Sort]] = {
    sort.key: sort
    for sort in (
        Sort(
            APIARY,
            False,
            48,
            1000,
            "the keeper shuts the hives, which takes a night's warning",
        ),
        Sort(
            ORGANIC,
            False,
            24,
            300,
            "a drift event costs the grower a certification, not a crop",
        ),
        Sort(
            SENSITIVE,
            False,
            48,
            300,
            "somebody has asked to be told, and being told is the whole of it",
        ),
        Sort(
            AQUACULTURE,
            True,
            500,
            0,
            "a pyrethroid in the raceway kills the stock, and notice changes nothing",
        ),
        Sort(
            WATER,
            True,
            500,
            0,
            "the label forbids it over open water whatever anybody has been told",
        ),
    )
}


def sort_of(kind: str) -> Sort:
    """One kind of register entry by name."""
    try:
        return SORTS[kind]
    except KeyError as exc:
        raise UsageError(f"{kind} is not a kind of entry: try {', '.join(SORTS)}") from exc


def kinds() -> list[str]:
    """Every kind of entry, for a command line choice."""
    return list(SORTS)


@dataclass(frozen=True)
class Exclusion:
    """One place on the register."""

    id: str
    kind: str
    name: str
    zone: str
    listed_on: dt.date
    contact: str = ""
    phone: str = ""
    buffer_ft: int = 0
    notice_hours: int = 0
    removed_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("exclusion", self.id)
        ids.require("zone", self.zone)
        sort_of(self.kind)
        if not self.name.strip():
            raise UsageError("a register entry needs a name")
        if self.buffer_ft < 0 or self.notice_hours < 0:
            raise UsageError("a buffer and a notice period cannot be negative")
        if self.removed_on is not None and self.removed_on < self.listed_on:
            raise UsageError("an entry cannot come off before it went on")
        if self.sort.absolute and not self.contact.strip() and self.kind == AQUACULTURE:
            raise UsageError("an aquaculture entry needs somebody to talk to")

    @property
    def sort(self) -> Sort:
        """What kind of entry this is."""
        return sort_of(self.kind)

    @property
    def absolute(self) -> bool:
        """Whether no amount of notice makes spraying acceptable."""
        return self.sort.absolute

    @property
    def hours(self) -> int:
        """Notice this entry wants, which is its own or its kind's."""
        return self.notice_hours or self.sort.notice_hours

    @property
    def buffer(self) -> int:
        """Buffer in feet, which is its own or its kind's."""
        return self.buffer_ft or self.sort.buffer_ft

    def on_register(self, on: dt.date) -> bool:
        """Whether the entry was on the register on a day."""
        if on < self.listed_on:
            return False
        return self.removed_on is None or on <= self.removed_on

    def notice_by(self, spray_at: dt.datetime) -> dt.datetime:
        """The latest moment notice could be given for a run."""
        return spray_at - dt.timedelta(hours=self.hours)

    def line(self) -> str:
        """One line for a register sheet."""
        how = "never sprayed over" if self.absolute else f"{self.hours} hours notice"
        return f"{self.id}  {self.kind}  {self.name}  {self.buffer} ft  {how}"

    @classmethod
    def from_row(cls, row: Row) -> Exclusion:
        """Read a register entry off a database row."""
        removed = row["removed_on"]
        return cls(
            id=str(row["id"]),
            kind=str(row["kind"]),
            name=str(row["name"]),
            zone=str(row["zone"]),
            listed_on=dt.date.fromisoformat(str(row["listed_on"])),
            contact=str(row["contact"]),
            phone=str(row["phone"]),
            buffer_ft=int(row["buffer_ft"]),
            notice_hours=int(row["notice_hours"]),
            removed_on=None if removed is None else dt.date.fromisoformat(str(removed)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this entry would be written as."""
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "zone": self.zone,
            "listed_on": self.listed_on.isoformat(),
            "contact": self.contact,
            "phone": self.phone,
            "buffer_ft": self.buffer_ft,
            "notice_hours": self.notice_hours,
            "removed_on": None if self.removed_on is None else self.removed_on.isoformat(),
            "note": self.note,
        }
