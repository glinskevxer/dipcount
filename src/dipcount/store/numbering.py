"""Reading back the identifiers a table already holds.

Twenty places in this package wanted the same two queries, and four of them
had written the dated one differently: two matched on a like pattern against
the whole id, one matched on the prefix alone, and one had the date format an
underscore out. Every one of them worked, because they were only ever asked
about a table their own module writes.

The ones that matter are the arguments to :mod:`dipcount.ids`, which mints the
next free number from what is taken. A list that misses an id already issued
mints it again, and a primary key refuses the second one at some point later
in the same round.
"""

from __future__ import annotations

import datetime as dt

from dipcount import ids
from dipcount.errors import UsageError
from dipcount.store.book import Book


def taken(book: Book, table: str) -> list[str]:
    """Every identifier a table already holds."""
    return [str(row["id"]) for row in book.all(f"SELECT id FROM {table} ORDER BY id")]


def taken_on(book: Book, table: str, kind: str, on: dt.date) -> list[str]:
    """Every dated identifier a table holds for one day.

    A kind whose numbers carry no date is refused rather than answered with
    nothing, because nothing is what a caller would get either way and only
    one of those is the truth.
    """
    sort = ids.kind_of(kind)
    if sort.style != ids.DATED:
        raise UsageError(f"{kind} numbers carry no date to list them by")
    stem = f"{sort.prefix}-{on:%y%m%d}-"
    rows = book.all(
        f"SELECT id FROM {table} WHERE id LIKE ? ORDER BY id",
        (f"{stem}%",),
    )
    return [str(row["id"]) for row in rows]


def next_serial(book: Book, table: str, kind: str) -> str:
    """The next free serial identifier for a table."""
    return ids.next_serial(kind, taken(book, table))


def next_dated(book: Book, table: str, kind: str, on: dt.date) -> str:
    """The next free dated identifier for a table on one day."""
    return ids.next_dated(kind, on, taken_on(book, table, kind, on))
