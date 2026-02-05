"""One line of the audit trail.

The district is a public body spending public money on pesticide, so the
question "who changed this record and when" has to have an answer that does
not depend on anybody remembering. Every write that matters puts a line here,
and nothing ever edits or deletes one.

The moment is stored in UTC and printed in the district's zone, which is the
rule everywhere in this package: a trail read back in November should not
appear to have happened an hour earlier than it did.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.rows import Row


@dataclass(frozen=True)
class Entry:
    """One recorded change."""

    seq: int
    at: dt.datetime
    actor: str
    action: str
    subject: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.actor.strip():
            raise UsageError("an audit line needs somebody's name against it")
        if not self.action.strip():
            raise UsageError("an audit line needs an action")
        if self.at.tzinfo is None:
            raise UsageError("an audit line needs a moment with a zone")

    def local(self, zone: str = clock.DEFAULT_ZONE) -> dt.datetime:
        """The moment this happened, in the district's zone."""
        return clock.in_zone(self.at, zone)

    def line(self, zone: str = clock.DEFAULT_ZONE) -> str:
        """The line a report prints."""
        tail = f"  {self.detail}" if self.detail else ""
        return f"{clock.stamp(self.at, zone)}  {self.actor}  {self.action} {self.subject}{tail}"

    @classmethod
    def from_row(cls, row: Row) -> Entry:
        """Read an entry off a database row."""
        return cls(
            seq=int(row["seq"]),
            at=dt.datetime.fromisoformat(str(row["at"])),
            actor=str(row["actor"]),
            action=str(row["action"]),
            subject=str(row["subject"]),
            detail=str(row["detail"]),
        )
