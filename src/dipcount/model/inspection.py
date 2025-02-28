"""An inspection: somebody stood at a site and looked at the water.

The record has to hold the negative result as firmly as the positive one. A
site that was dry on Tuesday is not a site nobody visited on Tuesday, and the
difference decides whether the next visit is in four days or in three weeks.
So ``water`` is a fact of its own and an inspection with no larvae lines is a
complete record rather than an unfinished one.

Larvae are counted by stage because the stage is the clock. First and second
instars mean the treatment window is open. Fourth instars and pupae mean it is
closing, and pupae will not eat anything the district can put in the water, so
a pupal count is a note that this brood is already lost.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from dipcount import clock, ids
from dipcount.errors import UsageError
from dipcount.store.book import Row

STAGES = ("R", "1", "2", "3", "4", "P")
"""Egg raft, the four larval instars, and pupa."""

EARLY = ("1", "2")
LATE = ("3", "4")
LARVAL = ("1", "2", "3", "4")


def stage_name(stage: str) -> str:
    """What a stage code is called out loud."""
    if stage == "R":
        return "egg raft"
    if stage == "P":
        return "pupa"
    return f"instar {stage}"


@dataclass(frozen=True)
class Tally:
    """How many of one species at one stage came out of the dipper."""

    species: str
    stage: str
    tally: int

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise UsageError(f"{self.stage} is not a stage: try {', '.join(STAGES)}")
        if self.tally < 0:
            raise UsageError("a tally cannot be negative")

    @property
    def is_larval(self) -> bool:
        """Whether this line counts something a larvicide would reach."""
        return self.stage in LARVAL

    @classmethod
    def from_row(cls, row: Row) -> Tally:
        """Read a tally off a database row."""
        return cls(str(row["species"]), str(row["stage"]), int(row["tally"]))


@dataclass(frozen=True)
class Inspection:
    """One visit to one site, and what the dipper found."""

    id: str
    site: str
    at: dt.datetime
    inspector: str
    water: bool
    dips: int = 0
    note: str = ""
    tallies: tuple[Tally, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ids.require("inspection", self.id)
        ids.require("site", self.site)
        if not self.inspector.strip():
            raise UsageError("an inspection needs the inspector's name")
        if self.at.tzinfo is None:
            raise UsageError("an inspection needs a moment with a zone")
        if self.dips < 0:
            raise UsageError("a negative number of dips is not a number of dips")
        if not self.water and self.dips:
            raise UsageError("a dry site cannot have been dipped")
        if not self.water and self.tallies:
            raise UsageError("a dry site cannot have produced larvae")
        if self.tallies and not self.dips:
            raise UsageError("larvae were counted but no dips were recorded")

    @property
    def on(self) -> dt.date:
        """The local day this inspection happened."""
        return clock.in_zone(self.at).date()

    @property
    def week(self) -> str:
        """The reporting week this inspection falls in."""
        return clock.week_label(self.on)

    def total(self, stages: tuple[str, ...] = LARVAL) -> int:
        """How many were counted across a set of stages."""
        return sum(one.tally for one in self.tallies if one.stage in stages)

    @property
    def larvae(self) -> int:
        """Every larva counted, of any instar and any species."""
        return self.total(LARVAL)

    @property
    def pupae(self) -> int:
        """Every pupa counted."""
        return self.total(("P",))

    @property
    def rafts(self) -> int:
        """Every egg raft counted."""
        return self.total(("R",))

    @property
    def per_dip(self) -> Decimal:
        """Larvae per dip, which is the number the threshold is written in."""
        if not self.dips:
            return Decimal(0)
        return Decimal(self.larvae) / Decimal(self.dips)

    @property
    def pupal_share(self) -> Decimal:
        """What share of the immatures are already past treating."""
        immatures = self.larvae + self.pupae
        if not immatures:
            return Decimal(0)
        return Decimal(self.pupae) / Decimal(immatures)

    @property
    def late_share(self) -> Decimal:
        """What share of the larvae are third or fourth instar."""
        if not self.larvae:
            return Decimal(0)
        return Decimal(self.total(LATE)) / Decimal(self.larvae)

    @property
    def positive(self) -> bool:
        """Whether anything at all came out of the water."""
        return bool(self.larvae or self.pupae or self.rafts)

    def species_seen(self) -> list[str]:
        """Every species code named on this inspection, in order."""
        found = {one.species for one in self.tallies if one.species}
        return sorted(found)

    def by_species(self, code: str, stages: tuple[str, ...] = LARVAL) -> int:
        """How many of one species were counted across a set of stages."""
        return sum(one.tally for one in self.tallies if one.species == code and one.stage in stages)

    @classmethod
    def from_row(cls, row: Row, tallies: tuple[Tally, ...] = ()) -> Inspection:
        """Read an inspection off a database row and its tally rows."""
        return cls(
            id=str(row["id"]),
            site=str(row["site"]),
            at=dt.datetime.fromisoformat(str(row["at"])),
            inspector=str(row["inspector"]),
            water=bool(row["water"]),
            dips=int(row["dips"]),
            note=str(row["note"]),
            tallies=tallies,
        )

    def to_row(self) -> dict[str, object]:
        """The row this inspection would be written as."""
        return {
            "id": self.id,
            "site": self.site,
            "at": clock.to_utc(self.at).isoformat(),
            "inspector": self.inspector,
            "water": int(self.water),
            "dips": self.dips,
            "note": self.note,
        }
