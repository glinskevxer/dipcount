"""The people who make applications, and what they are allowed to make.

A pesticide licence is not one thing. It has a grade, which says whether the
holder works on their own or under somebody, and it has categories, which say
what kind of work the licence covers. Public health is the one a mosquito
district lives on, and a licence in right of way work does not cover it
however many years the holder has been doing this.

Two clocks run at once and they are easy to confuse. The licence expires on a
date, and after that date the holder makes no applications of any kind. The
recertification cycle wants a number of credit hours before that date, and a
holder who is short of hours in October is still licensed and still working;
they simply will not be renewed. Reporting them as unlicensed is wrong and
reporting them as fine is worse.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from dipcount import ids
from dipcount.errors import UsageError
from dipcount.rows import Row

CERTIFIED: Final = "certified"
TECHNICIAN: Final = "technician"
TRAINEE: Final = "trainee"
GRADES: Final = (CERTIFIED, TECHNICIAN, TRAINEE)

CORE: Final = "core"
PUBLIC_HEALTH: Final = "public health"
AQUATIC: Final = "aquatic"
RIGHT_OF_WAY: Final = "right of way"
CATEGORIES: Final = (CORE, PUBLIC_HEALTH, AQUATIC, RIGHT_OF_WAY)

CYCLE_YEARS: Final = 3
"""How long a certification runs before it has to be renewed."""

CREDIT_HOURS: Final[dict[str, str]] = {
    CERTIFIED: "18",
    TECHNICIAN: "9",
    TRAINEE: "0",
}
"""Credit hours a grade needs over one cycle."""


@dataclass(frozen=True)
class Credit:
    """One course sat, and what it counted for."""

    seq: int
    applicator: str
    on: dt.date
    category: str
    hours: Decimal
    course: str

    def __post_init__(self) -> None:
        ids.require("applicator", self.applicator)
        if self.category not in CATEGORIES:
            raise UsageError(f"{self.category} is not a category: try {', '.join(CATEGORIES)}")
        if self.hours <= 0:
            raise UsageError("a course worth no hours is not worth recording")
        if not self.course.strip():
            raise UsageError("a credit needs the name of the course")

    @classmethod
    def from_row(cls, row: Row) -> Credit:
        """Read a credit off a database row."""
        return cls(
            seq=int(row["seq"]),
            applicator=str(row["applicator"]),
            on=dt.date.fromisoformat(str(row["on_day"])),
            category=str(row["category"]),
            hours=Decimal(str(row["hours"])),
            course=str(row["course"]),
        )


@dataclass(frozen=True)
class Applicator:
    """One licence holder."""

    id: str
    name: str
    licence: str
    grade: str
    categories: tuple[str, ...]
    certified_on: dt.date
    expires_on: dt.date
    supervisor: str | None = None
    left_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("applicator", self.id)
        if not self.name.strip():
            raise UsageError("an applicator needs a name")
        if not self.licence.strip():
            raise UsageError("an applicator needs a licence number")
        if self.grade not in GRADES:
            raise UsageError(f"{self.grade} is not a grade: try {', '.join(GRADES)}")
        if not self.categories:
            raise UsageError("a licence with no categories covers nothing")
        for one in self.categories:
            if one not in CATEGORIES:
                raise UsageError(f"{one} is not a category")
        if self.expires_on <= self.certified_on:
            raise UsageError("a licence cannot expire before it was issued")
        if self.supervisor is not None:
            ids.require("applicator", self.supervisor)
        if self.grade != CERTIFIED and self.supervisor is None:
            raise UsageError(f"a {self.grade} works under a certified applicator")
        if self.grade == CERTIFIED and self.supervisor is not None:
            raise UsageError("a certified applicator does not work under anybody")

    @property
    def hours_needed(self) -> Decimal:
        """Credit hours this grade needs over a cycle."""
        return Decimal(CREDIT_HOURS[self.grade])

    def licensed(self, on: dt.date) -> bool:
        """Whether the licence is in date on a day."""
        if on < self.certified_on or on > self.expires_on:
            return False
        return self.left_on is None or on <= self.left_on

    def covers(self, category: str) -> bool:
        """Whether the licence covers a kind of work."""
        return category in self.categories

    def may_apply(self, on: dt.date, category: str, *, restricted: bool) -> bool:
        """Whether this person may make one kind of application on a day.

        A restricted use pesticide needs a certified applicator. Anything else
        may be applied by a technician, who is working under one.
        """
        if not self.licensed(on) or not self.covers(category):
            return False
        if restricted:
            return self.grade == CERTIFIED
        return self.grade in (CERTIFIED, TECHNICIAN)

    def cycle_start(self) -> dt.date:
        """The day the current recertification cycle opened."""
        return dt.date(
            self.expires_on.year - CYCLE_YEARS,
            self.expires_on.month,
            self.expires_on.day,
        )

    @classmethod
    def from_row(cls, row: Row) -> Applicator:
        """Read an applicator off a database row."""
        left = row["left_on"]
        supervisor = row["supervisor"]
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            licence=str(row["licence"]),
            grade=str(row["grade"]),
            categories=tuple(str(row["categories"]).split(",")),
            certified_on=dt.date.fromisoformat(str(row["certified_on"])),
            expires_on=dt.date.fromisoformat(str(row["expires_on"])),
            supervisor=None if supervisor is None else str(supervisor),
            left_on=None if left is None else dt.date.fromisoformat(str(left)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this applicator would be written as."""
        return {
            "id": self.id,
            "name": self.name,
            "licence": self.licence,
            "grade": self.grade,
            "categories": ",".join(self.categories),
            "certified_on": self.certified_on.isoformat(),
            "expires_on": self.expires_on.isoformat(),
            "supervisor": self.supervisor,
            "left_on": None if self.left_on is None else self.left_on.isoformat(),
            "note": self.note,
        }
