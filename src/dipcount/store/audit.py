"""Writing and reading the audit trail."""

from __future__ import annotations

import datetime as dt

from dipcount import clock
from dipcount.errors import NotFound
from dipcount.model.audit import Entry
from dipcount.store import window
from dipcount.store.book import Book

_COLUMNS = "seq, at, actor, action, subject, detail"


def record(
    book: Book,
    actor: str,
    action: str,
    subject: str,
    detail: str = "",
    at: dt.datetime | None = None,
) -> Entry:
    """Put one line on the trail."""
    when = clock.to_utc(at if at is not None else clock.now())
    entry = Entry(0, when, actor, action, subject, detail)
    cursor = book.run(
        "INSERT INTO audit (at, actor, action, subject, detail)"
        " VALUES (:at, :actor, :action, :subject, :detail)",
        {
            "at": when.isoformat(),
            "actor": entry.actor,
            "action": entry.action,
            "subject": entry.subject,
            "detail": entry.detail,
        },
    )
    return get(book, int(cursor.lastrowid or 0))


def get(book: Book, seq: int) -> Entry:
    """One line by its sequence number."""
    row = book.one(f"SELECT {_COLUMNS} FROM audit WHERE seq = ?", (seq,))
    if row is None:
        raise NotFound("audit line", str(seq))
    return Entry.from_row(row)


def about(book: Book, subject: str) -> list[Entry]:
    """Every line about one record, oldest first."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM audit WHERE subject = ? ORDER BY seq",
        (subject,),
    )
    return [Entry.from_row(row) for row in rows]


def between(book: Book, start: dt.datetime, end: dt.datetime) -> list[Entry]:
    """Every line in a window, oldest first."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM audit WHERE at >= ? AND at < ? ORDER BY seq",
        (window.from_moment(start), window.from_moment(end)),
    )
    return [Entry.from_row(row) for row in rows]


def on_day(book: Book, on: dt.date, zone: str = clock.DEFAULT_ZONE) -> list[Entry]:
    """Every line written on one local day."""
    start = clock.moment(f"{on.isoformat()} 00:00", zone)
    return between(book, start, start + dt.timedelta(days=1))


def by_actor(book: Book, actor: str) -> list[Entry]:
    """Every line one person wrote, oldest first."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM audit WHERE actor = ? ORDER BY seq",
        (actor,),
    )
    return [Entry.from_row(row) for row in rows]


def walk(book: Book, limit: int = 0) -> list[Entry]:
    """The whole trail, newest last, optionally only the last few."""
    if limit > 0:
        rows = book.all(
            f"SELECT {_COLUMNS} FROM (SELECT {_COLUMNS} FROM audit"
            " ORDER BY seq DESC LIMIT ?) ORDER BY seq",
            (limit,),
        )
    else:
        rows = book.all(f"SELECT {_COLUMNS} FROM audit ORDER BY seq")
    return [Entry.from_row(row) for row in rows]


def actions(book: Book) -> list[str]:
    """Every distinct action the trail holds."""
    rows = book.all("SELECT DISTINCT action FROM audit ORDER BY action")
    return [str(row["action"]) for row in rows]
