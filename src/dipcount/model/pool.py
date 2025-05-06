"""Pools sent to the laboratory, and the results that come back.

A pool is up to fifty females of one species out of one jar, ground up
together and tested as a unit. That is what makes virus surveillance
affordable and it is also what makes the arithmetic awkward: a positive pool
says at least one of the fifty was carrying, not how many, so the infection
rate has to be estimated rather than counted.

A result is one virus against one pool. The same pool is usually run for
several viruses at once and they come back separately, so a pool with a West
Nile result and nothing yet for eastern equine is an ordinary state of
affairs rather than a half filled record. Anything that reports on a virus
looks at the results for that virus and leaves the rest alone.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Final

from dipcount import ids, species
from dipcount.errors import UsageError
from dipcount.species import Species
from dipcount.store.book import Row

POSITIVE: Final = "positive"
NEGATIVE: Final = "negative"
UNSATISFACTORY: Final = "unsatisfactory"
PENDING: Final = "pending"
OUTCOMES: Final = (POSITIVE, NEGATIVE, UNSATISFACTORY, PENDING)

MAX_POOL: Final = 50
"""The most mosquitoes the laboratory will take in one pool."""


@dataclass(frozen=True)
class Assay:
    """One virus run against one pool."""

    virus: str
    outcome: str
    tested_on: dt.date | None = None
    ct: float | None = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise UsageError(f"{self.outcome} is not an outcome: try {', '.join(OUTCOMES)}")
        if self.virus not in species.viruses():
            raise UsageError(f"{self.virus} is not a virus this district tests for")
        if self.outcome == PENDING and self.tested_on is not None:
            raise UsageError("a pending result cannot have been tested")
        if self.outcome != PENDING and self.tested_on is None:
            raise UsageError(f"a {self.outcome} result needs the day it was tested")
        if self.ct is not None and self.outcome != POSITIVE:
            raise UsageError("only a positive result carries a cycle threshold")

    @property
    def counts(self) -> bool:
        """Whether this result belongs in an infection rate at all.

        An unsatisfactory pool is one the laboratory could not read. It is
        neither a positive nor a negative and it is left out of both halves,
        the same way a trap that did not run is left out of an index.
        """
        return self.outcome in (POSITIVE, NEGATIVE)

    @classmethod
    def from_row(cls, row: Row) -> Assay:
        """Read a result off a database row."""
        tested = row["tested_on"]
        return cls(
            virus=str(row["virus"]),
            outcome=str(row["outcome"]),
            tested_on=None if tested is None else dt.date.fromisoformat(str(tested)),
            ct=None if row["ct"] is None else float(row["ct"]),
        )


@dataclass(frozen=True)
class Pool:
    """One vial of one species out of one jar."""

    id: str
    collection: str
    species: str
    size: int
    submitted_on: dt.date
    lab: str = ""
    note: str = ""
    assays: tuple[Assay, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ids.require("pool", self.id)
        ids.require("collection", self.collection)
        species.species(self.species)
        if self.size < 1:
            raise UsageError("a pool of nothing is not a pool")
        if self.size > MAX_POOL:
            raise UsageError(f"{self.size} is over the {MAX_POOL} the laboratory will take")
        if len({one.virus for one in self.assays}) != len(self.assays):
            raise UsageError("a pool cannot hold two results for one virus")

    @property
    def sort(self) -> Species:
        """The species in this pool.

        The annotation names ``Species`` directly rather than through the
        module, because the field on this class is also called ``species`` and
        an annotation is read in the class body where the field wins.
        """
        return species.species(self.species)

    def result(self, virus: str) -> Assay | None:
        """The result for one virus, or nothing if it has not been run."""
        for one in self.assays:
            if one.virus == virus:
                return one
        return None

    def outcome(self, virus: str) -> str:
        """What one virus came back as, which is pending until it has."""
        found = self.result(virus)
        return PENDING if found is None else found.outcome

    def is_positive(self, virus: str) -> bool:
        """Whether this pool came back positive for one virus."""
        return self.outcome(virus) == POSITIVE

    def counts_for(self, virus: str) -> bool:
        """Whether this pool belongs in an infection rate for one virus."""
        found = self.result(virus)
        return found is not None and found.counts

    def could_carry(self, virus: str) -> bool:
        """Whether the species in this pool is a vector of the virus at all."""
        return self.sort.carries_virus(virus)

    @classmethod
    def from_row(cls, row: Row, assays: tuple[Assay, ...] = ()) -> Pool:
        """Read a pool off a database row and its result rows."""
        return cls(
            id=str(row["id"]),
            collection=str(row["collection"]),
            species=str(row["species"]),
            size=int(row["size"]),
            submitted_on=dt.date.fromisoformat(str(row["submitted_on"])),
            lab=str(row["lab"]),
            note=str(row["note"]),
            assays=assays,
        )

    def to_row(self) -> dict[str, object]:
        """The row this pool would be written as."""
        return {
            "id": self.id,
            "collection": self.collection,
            "species": self.species,
            "size": self.size,
            "submitted_on": self.submitted_on.isoformat(),
            "lab": self.lab,
            "note": self.note,
        }
