"""A site: one piece of water the district has on its list.

The extent is a quantity rather than a number because the unit is load
bearing. A catch basin site is fourteen structures and a marsh is six acres,
and a rate written for one of those cannot be applied over the other. The
habitat says which unit the extent has to be in, and a site that disagrees
with its own habitat is refused here rather than at the point of treatment.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dipcount import habitat as hb
from dipcount import ids
from dipcount.errors import UsageError
from dipcount.store.book import Row
from dipcount.units import Quantity


@dataclass(frozen=True)
class Site:
    """One inspected piece of water."""

    id: str
    zone: str
    name: str
    habitat: str
    extent: Quantity
    listed_on: dt.date
    access: str = ""
    latitude: float | None = None
    longitude: float | None = None
    retired_on: dt.date | None = None
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("site", self.id)
        ids.require("zone", self.zone)
        if not self.name.strip():
            raise UsageError("a site needs a name")
        kind = hb.habitat(self.habitat)
        if self.extent.unit != kind.extent_unit:
            raise UsageError(
                f"a {kind.name} is measured in {kind.extent_unit}"
                f" and this one says {self.extent.unit}",
            )
        if self.extent.amount <= 0:
            raise UsageError("a site with no extent is not a site")
        if self.retired_on is not None and self.retired_on < self.listed_on:
            raise UsageError("a site cannot be retired before it was listed")
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise UsageError(f"{self.latitude} is not a latitude")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise UsageError(f"{self.longitude} is not a longitude")

    @property
    def kind(self) -> hb.Habitat:
        """The habitat this site is."""
        return hb.habitat(self.habitat)

    def is_open(self, on: dt.date) -> bool:
        """Whether the site was on the list on a given day."""
        if on < self.listed_on:
            return False
        return self.retired_on is None or on <= self.retired_on

    def due_after(self, last_seen: dt.date) -> dt.date:
        """When this site is next due for an inspection."""
        return last_seen + dt.timedelta(days=self.kind.interval_days)

    @classmethod
    def from_row(cls, row: Row) -> Site:
        """Read a site off a database row."""
        retired = row["retired_on"]
        return cls(
            id=str(row["id"]),
            zone=str(row["zone"]),
            name=str(row["name"]),
            habitat=str(row["habitat"]),
            extent=Quantity.parse(str(row["extent"])),
            listed_on=dt.date.fromisoformat(str(row["listed_on"])),
            access=str(row["access"]),
            latitude=None if row["latitude"] is None else float(row["latitude"]),
            longitude=None if row["longitude"] is None else float(row["longitude"]),
            retired_on=None if retired is None else dt.date.fromisoformat(str(retired)),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, object]:
        """The row this site would be written as."""
        return {
            "id": self.id,
            "zone": self.zone,
            "name": self.name,
            "habitat": self.habitat,
            "extent": str(self.extent),
            "listed_on": self.listed_on.isoformat(),
            "access": self.access,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "retired_on": None if self.retired_on is None else self.retired_on.isoformat(),
            "note": self.note,
        }
