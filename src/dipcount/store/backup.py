"""Taking a copy of the book while somebody is still writing to it.

Copying a sqlite file with the filesystem is safe only when nothing is writing
to it, and the one time a district takes a backup is the evening the round
comes in, which is exactly when something is. Sqlite's own backup walks the
pages under a read lock and produces a file that is consistent whether or not
a write lands halfway through.

The verify step is the part districts skip. A backup nobody has opened is a
file, not a backup: the failure mode is a truncated copy that looks the right
size, and the first anybody hears of it is the morning after the disk went.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from dipcount import clock
from dipcount.errors import BookError
from dipcount.store.book import Book
from dipcount.store.migrations import latest


@dataclass(frozen=True)
class Copy:
    """One backup, and what was found when it was opened again."""

    path: Path
    at: dt.datetime
    bytes_written: int
    tables: int
    rows: int
    version: int

    @property
    def sound(self) -> bool:
        """Whether the copy opened and read back as a migrated book."""
        return self.version == latest() and self.tables > 0

    def line(self) -> str:
        """One line for a log."""
        return (
            f"{clock.stamp(self.at)}  {self.path}"
            f"  {self.bytes_written} bytes, {self.tables} tables, {self.rows} rows"
            f"  {'sound' if self.sound else 'NOT SOUND'}"
        )


def name_for(on: dt.datetime, stem: str = "district") -> str:
    """What a backup taken at a moment is called."""
    return f"{stem}-{clock.in_zone(on):%Y%m%d-%H%M}.sqlite3"


def take(book: Book, into: Path, *, at: dt.datetime | None = None) -> Copy:
    """Copy the book, then open the copy and count what is in it."""
    when = at if at is not None else clock.now()
    into.mkdir(parents=True, exist_ok=True)
    path = into / name_for(when)
    target = sqlite3.connect(str(path))
    try:
        book.backup(target)
    finally:
        target.close()
    return verify(path, when)


def verify(path: Path, at: dt.datetime | None = None) -> Copy:
    """Open a backup and say what is in it."""
    if not path.exists():
        raise BookError(f"there is no backup at {path}")
    opened = Book(path)
    try:
        tables = opened.tables()
        rows = sum(opened.count(one) for one in tables)
        return Copy(
            path=path,
            at=at if at is not None else clock.now(),
            bytes_written=path.stat().st_size,
            tables=len(tables),
            rows=rows,
            version=opened.version,
        )
    finally:
        opened.close()


def kept(into: Path) -> list[Path]:
    """Every backup in a directory, oldest first by name."""
    if not into.exists():
        return []
    return sorted(into.glob("*.sqlite3"))


def prune(into: Path, keep: int) -> list[Path]:
    """Delete all but the newest few backups, and say what went."""
    if keep < 1:
        raise BookError("a backup rota that keeps nothing is not a rota")
    held = kept(into)
    gone = held[: max(len(held) - keep, 0)]
    for one in gone:
        one.unlink()
    return gone
