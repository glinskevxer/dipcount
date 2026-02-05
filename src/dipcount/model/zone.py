"""A zone: the piece of the district one supervisor answers for."""

from __future__ import annotations

from dataclasses import dataclass

from dipcount import ids
from dipcount.errors import UsageError
from dipcount.rows import Row


@dataclass(frozen=True)
class Zone:
    """One operational zone of the district."""

    id: str
    name: str
    supervisor: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        ids.require("zone", self.id)
        if not self.name.strip():
            raise UsageError("a zone needs a name")

    @classmethod
    def from_row(cls, row: Row) -> Zone:
        """Read a zone off a database row."""
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            supervisor=str(row["supervisor"]),
            note=str(row["note"]),
        )

    def to_row(self) -> dict[str, str]:
        """The row this zone would be written as."""
        return {
            "id": self.id,
            "name": self.name,
            "supervisor": self.supervisor,
            "note": self.note,
        }
