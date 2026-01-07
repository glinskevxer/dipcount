"""Bottle bioassays: whether what the district sprays still works.

Mosquitoes go into bottles coated with a diagnostic dose of one active
ingredient, and somebody counts how many are knocked down at set minutes. At
the diagnostic time a susceptible population is flat. What is left standing is
the finding.

The control bottle is the part that is easy to get wrong. It has no
insecticide in it, so anything dying in it died of handling: heat, rough
aspiration, a long drive back from the field. A little of that is ordinary and
is corrected for with Abbott's formula, which asks what share of the survivors
the treatment killed rather than what share of the whole. Too much of it and
there is nothing to correct: the mosquitoes were dying anyway and the assay
says nothing about the insecticide at all. Those are different outcomes and
the band between them is where the judgement sits.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from dipcount import ids, species
from dipcount.errors import UsageError
from dipcount.store.book import Row

CONTROL: Final = "control"

FIELD: Final = "field"
COLONY: Final = "colony"
SOURCES: Final = (FIELD, COLONY)

SUSCEPTIBLE: Final = "susceptible"
POSSIBLE: Final = "possible resistance"
RESISTANT: Final = "resistant"
VOID: Final = "void"

SUSCEPTIBLE_AT: Final = Decimal("98")
"""Corrected mortality at or above this is a susceptible population."""

RESISTANT_UNDER: Final = Decimal("90")
"""Corrected mortality under this is resistance."""

CONTROL_CORRECT: Final = Decimal("5")
"""Control mortality at or above this is corrected for."""

CONTROL_VOID: Final = Decimal("20")
"""Control mortality over this makes the whole assay say nothing."""


def abbott(treated: Decimal, control: Decimal) -> Decimal:
    """Mortality corrected for what died in the control bottle."""
    if control >= 100:
        raise UsageError("a control that killed everything corrects nothing")
    return (treated - control) / (Decimal(100) - control) * Decimal(100)


@dataclass(frozen=True)
class Reading:
    """How many were down in one bottle at one minute."""

    label: str
    minute: int
    knocked: int
    total: int

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise UsageError("a reading needs a bottle to belong to")
        if self.minute < 0:
            raise UsageError("a reading cannot be taken before the assay starts")
        if self.total < 1:
            raise UsageError("an empty bottle is not a bottle")
        if not 0 <= self.knocked <= self.total:
            raise UsageError(f"{self.knocked} down out of {self.total} is not a count")

    @property
    def is_control(self) -> bool:
        """Whether this bottle had no insecticide in it."""
        return self.label == CONTROL

    @property
    def share(self) -> Decimal:
        """What share of the bottle was down, as a percentage."""
        return Decimal(self.knocked) / Decimal(self.total) * Decimal(100)

    @classmethod
    def from_row(cls, row: Row) -> Reading:
        """Read a bottle reading off a database row."""
        return cls(
            label=str(row["label"]),
            minute=int(row["minute"]),
            knocked=int(row["knocked"]),
            total=int(row["total"]),
        )


@dataclass(frozen=True)
class Bioassay:
    """One run of bottles against one active ingredient."""

    id: str
    active: str
    species: str
    source: str
    on: dt.date
    tested_by: str
    dose_ug: float
    diagnostic: int
    zone: str | None = None
    note: str = ""
    readings: tuple[Reading, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ids.require("bioassay", self.id)
        species.species(self.species)
        if self.source not in SOURCES:
            raise UsageError(f"{self.source} is not a source: try {', '.join(SOURCES)}")
        if not self.active.strip():
            raise UsageError("an assay needs an active ingredient")
        if not self.tested_by.strip():
            raise UsageError("an assay needs the name of whoever ran it")
        if self.dose_ug <= 0:
            raise UsageError("a bottle with no dose in it is a control, not an assay")
        if self.diagnostic <= 0:
            raise UsageError("a diagnostic time has to be a number of minutes")
        if self.zone is not None:
            ids.require("zone", self.zone)
        if ids.day_of(self.id) != self.on:
            raise UsageError(f"{self.id} does not carry {self.on.isoformat()}")
        seen = {(one.label, one.minute) for one in self.readings}
        if len(seen) != len(self.readings):
            raise UsageError("one bottle cannot be read twice at one minute")

    def at(self, minute: int) -> list[Reading]:
        """Every bottle read at one minute."""
        return [one for one in self.readings if one.minute == minute]

    def minutes(self) -> list[int]:
        """Every minute anything was read at, in order."""
        return sorted({one.minute for one in self.readings})

    def treated_share(self, minute: int) -> Decimal | None:
        """What share of the treated bottles were down at a minute."""
        found = [one for one in self.at(minute) if not one.is_control]
        if not found:
            return None
        knocked = sum(one.knocked for one in found)
        total = sum(one.total for one in found)
        return Decimal(knocked) / Decimal(total) * Decimal(100)

    def control_share(self, minute: int) -> Decimal | None:
        """What share of the control bottle was down at a minute."""
        found = [one for one in self.at(minute) if one.is_control]
        if not found:
            return None
        knocked = sum(one.knocked for one in found)
        total = sum(one.total for one in found)
        return Decimal(knocked) / Decimal(total) * Decimal(100)

    def mortality(self) -> Decimal | None:
        """Corrected mortality at the diagnostic time.

        Under the correction floor the raw figure stands. Inside the band it
        is corrected. Over the ceiling nothing is returned, because there is
        nothing the assay can be said to have measured.
        """
        treated = self.treated_share(self.diagnostic)
        if treated is None:
            return None
        control = self.control_share(self.diagnostic)
        if control is None or control < CONTROL_CORRECT:
            return treated
        if control > CONTROL_VOID:
            return None
        return abbott(treated, control)

    def verdict(self) -> str:
        """What the assay says about the population."""
        found = self.mortality()
        if found is None:
            return VOID
        if found >= SUSCEPTIBLE_AT:
            return SUSCEPTIBLE
        if found < RESISTANT_UNDER:
            return RESISTANT
        return POSSIBLE

    def corrected(self) -> bool:
        """Whether Abbott's correction was applied."""
        control = self.control_share(self.diagnostic)
        return control is not None and CONTROL_CORRECT <= control <= CONTROL_VOID

    def line(self) -> str:
        """One line for a resistance sheet."""
        found = self.mortality()
        figure = "no reading" if found is None else f"{found:.1f} percent"
        return (
            f"{self.id}  {self.species}  {self.active}  {self.dose_ug:g} ug"
            f"  at {self.diagnostic} min  {figure}  {self.verdict()}"
        )

    @classmethod
    def from_row(cls, row: Row, readings: tuple[Reading, ...] = ()) -> Bioassay:
        """Read an assay off a database row and its bottle rows."""
        zone = row["zone"]
        return cls(
            id=str(row["id"]),
            active=str(row["active"]),
            species=str(row["species"]),
            source=str(row["source"]),
            on=dt.date.fromisoformat(str(row["on_day"])),
            tested_by=str(row["tested_by"]),
            dose_ug=float(row["dose_ug"]),
            diagnostic=int(row["diagnostic"]),
            zone=None if zone is None else str(zone),
            note=str(row["note"]),
            readings=readings,
        )

    def to_row(self) -> dict[str, object]:
        """The row this assay would be written as."""
        return {
            "id": self.id,
            "active": self.active,
            "species": self.species,
            "source": self.source,
            "zone": self.zone,
            "on_day": self.on.isoformat(),
            "tested_by": self.tested_by,
            "dose_ug": self.dose_ug,
            "diagnostic": self.diagnostic,
            "note": self.note,
        }
