"""The machines, and what a calibration says about them.

A fogger is calibrated for three things and they are not interchangeable. The
flow rate is how much comes out of the nozzle in a minute. The droplet
spectrum is how small the pieces are, which decides whether they hang in the
air long enough to hit a mosquito or fall on the grass. The swath is how wide
the cloud is by the time it settles, which with the driving speed decides how
many acres an hour the truck covers.

The number the label is written against comes out of all three. Ounces per
acre is flow divided by acres an hour, and acres an hour is speed times swath.
A machine flowing exactly to its nominal rate, driven ten miles an hour
instead of five, puts half the labelled rate on the ground and the paperwork
says it was right. That arithmetic is the whole point of this module.

The droplet size is where an ultra low volume machine either is one or is not.
Over the label's ceiling the cloud falls out of the air, the mosquitoes never
meet it, and what has happened is a pesticide application to somebody's lawn.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from dipcount import ids
from dipcount.errors import UsageError
from dipcount.store.book import Row
from dipcount.units import Quantity, Rate

FOGGER: Final = "ulv fogger"
MIST: Final = "backpack mist blower"
SPREADER: Final = "granule spreader"
BACKPACK: Final = "backpack sprayer"
DUSTER: Final = "hand duster"
KINDS: Final = (FOGGER, MIST, SPREADER, BACKPACK, DUSTER)

DROPLET_CEILING: Final = Decimal("30")
"""Volume median diameter in microns an ultra low volume machine has to beat."""

FLOW_TOLERANCE: Final = Decimal("0.10")
"""How far from nominal a flow rate may sit before the machine is out."""

CALIBRATION_DAYS: Final = 30
"""How long a calibration stands before the machine is checked again."""

ACRE_FEET_PER_HOUR: Final = Decimal("8.25")
"""Miles an hour times swath feet, over this, is acres an hour."""


def acres_per_hour(speed_mph: float, swath_ft: float) -> Decimal:
    """How much ground a machine covers at a speed and a swath."""
    if speed_mph <= 0 or swath_ft <= 0:
        raise UsageError("a machine standing still covers no ground")
    return Decimal(str(speed_mph)) * Decimal(str(swath_ft)) / ACRE_FEET_PER_HOUR


def applied_rate(flow: Quantity, speed_mph: float, swath_ft: float) -> Rate:
    """What a machine actually puts on the ground, per acre.

    The flow is per minute, so it is multiplied up to the hour before it is
    divided by the acres an hour. Driving faster does not put more product
    down; it spreads the same flow over more ground.
    """
    covered = acres_per_hour(speed_mph, swath_ft)
    return Rate(flow * 60 / covered, "acre")


def speed_for(flow: Quantity, wanted: Rate, swath_ft: float) -> Decimal:
    """How fast to drive to hit a labelled rate at a measured flow."""
    if swath_ft <= 0:
        raise UsageError("a machine with no swath covers no ground")
    per_acre = wanted.amount.to(flow.unit).amount
    if per_acre <= 0:
        raise UsageError("a rate of nothing cannot be driven to")
    covered = flow.amount * 60 / per_acre
    return covered * ACRE_FEET_PER_HOUR / Decimal(str(swath_ft))


@dataclass(frozen=True)
class Machine:
    """One piece of application equipment."""

    id: str
    kind: str
    maker: str
    model: str
    serial: str
    added_on: dt.date
    nominal: Quantity | None = None
    swath_ft: float = 0.0
    retired_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("equipment", self.id)
        if self.kind not in KINDS:
            raise UsageError(f"{self.kind} is not a kind of machine: try {', '.join(KINDS)}")
        if not self.serial.strip():
            raise UsageError("a machine needs a serial number")
        if not self.model.strip():
            raise UsageError("a machine needs a model")
        if self.swath_ft < 0:
            raise UsageError("a swath cannot be negative")
        if self.retired_on is not None and self.retired_on < self.added_on:
            raise UsageError("a machine cannot be retired before it arrived")

    @property
    def is_ulv(self) -> bool:
        """Whether the droplet ceiling applies to this machine."""
        return self.kind in (FOGGER, MIST)

    def in_service(self, on: dt.date) -> bool:
        """Whether the machine was in service on a day."""
        if on < self.added_on:
            return False
        return self.retired_on is None or on <= self.retired_on

    @classmethod
    def from_row(cls, row: Row) -> Machine:
        """Read a machine off a database row."""
        retired = row["retired_on"]
        nominal = str(row["nominal"])
        return cls(
            id=str(row["id"]),
            kind=str(row["kind"]),
            maker=str(row["maker"]),
            model=str(row["model"]),
            serial=str(row["serial"]),
            added_on=dt.date.fromisoformat(str(row["added_on"])),
            nominal=Quantity.parse(nominal) if nominal else None,
            swath_ft=float(row["swath_ft"]),
            retired_on=None if retired is None else dt.date.fromisoformat(str(retired)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this machine would be written as."""
        return {
            "id": self.id,
            "kind": self.kind,
            "maker": self.maker,
            "model": self.model,
            "serial": self.serial,
            "nominal": "" if self.nominal is None else str(self.nominal),
            "swath_ft": self.swath_ft,
            "added_on": self.added_on.isoformat(),
            "retired_on": None if self.retired_on is None else self.retired_on.isoformat(),
            "note": self.note,
        }


@dataclass(frozen=True)
class Calibration:
    """One check of one machine on one day."""

    id: str
    equipment: str
    on: dt.date
    tested_by: str
    flow: Quantity
    droplet: float | None = None
    swath_ft: float = 0.0
    speed_mph: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("calibration", self.id)
        ids.require("equipment", self.equipment)
        if not self.tested_by.strip():
            raise UsageError("a calibration needs the name of whoever ran it")
        if self.flow.amount <= 0:
            raise UsageError("a machine flowing nothing has not been calibrated")
        if self.droplet is not None and self.droplet <= 0:
            raise UsageError("a droplet size cannot be negative")
        if self.swath_ft < 0 or self.speed_mph < 0:
            raise UsageError("a swath and a speed cannot be negative")
        if ids.day_of(self.id) != self.on:
            raise UsageError(f"{self.id} does not carry {self.on.isoformat()}")

    def within(self, nominal: Quantity) -> bool:
        """Whether the flow is close enough to what the machine should do."""
        low = nominal * (Decimal(1) - FLOW_TOLERANCE)
        high = nominal * (Decimal(1) + FLOW_TOLERANCE)
        return low <= self.flow <= high

    def droplet_ok(self, ulv: bool) -> bool:
        """Whether the droplet spectrum is inside the ceiling."""
        if not ulv:
            return True
        return self.droplet is not None and Decimal(str(self.droplet)) <= DROPLET_CEILING

    def rate(self) -> Rate | None:
        """What this calibration says goes on the ground, per acre."""
        if self.speed_mph <= 0 or self.swath_ft <= 0:
            return None
        return applied_rate(self.flow, self.speed_mph, self.swath_ft)

    def due(self) -> dt.date:
        """When the machine is next due to be checked."""
        return self.on + dt.timedelta(days=CALIBRATION_DAYS)

    @classmethod
    def from_row(cls, row: Row) -> Calibration:
        """Read a calibration off a database row."""
        return cls(
            id=str(row["id"]),
            equipment=str(row["equipment"]),
            on=dt.date.fromisoformat(str(row["on_day"])),
            tested_by=str(row["tested_by"]),
            flow=Quantity.parse(str(row["flow"])),
            droplet=None if row["droplet"] is None else float(row["droplet"]),
            swath_ft=float(row["swath_ft"]),
            speed_mph=float(row["speed_mph"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this calibration would be written as."""
        return {
            "id": self.id,
            "equipment": self.equipment,
            "on_day": self.on.isoformat(),
            "tested_by": self.tested_by,
            "flow": str(self.flow),
            "droplet": self.droplet,
            "swath_ft": self.swath_ft,
            "speed_mph": self.speed_mph,
            "note": self.note,
        }
