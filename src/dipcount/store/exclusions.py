"""Reading and writing the no spray register."""

from __future__ import annotations

import datetime as dt

from dipcount import ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.exclusion import Exclusion, sort_of
from dipcount.store import zones
from dipcount.store.book import Book

_COLUMNS = (
    "id, kind, name, zone, contact, phone, buffer_ft, notice_hours, listed_on, removed_on, note"
)
_VALUES = (
    ":id, :kind, :name, :zone, :contact, :phone, :buffer_ft, :notice_hours,"
    " :listed_on, :removed_on, :note"
)


def numbers(book: Book) -> list[str]:
    """Every register id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM exclusion")]


def add(
    book: Book,
    kind: str,
    name: str,
    zone_id: str,
    listed_on: dt.date,
    *,
    contact: str = "",
    phone: str = "",
    buffer_ft: int = 0,
    notice_hours: int = 0,
    note: str = "",
) -> Exclusion:
    """Put a place on the register."""
    sort_of(kind)
    zone = zones.resolve(book, zone_id)
    if find(book, kind, name) is not None:
        raise Duplicate("register entry", f"{kind} {name}")
    entry = Exclusion(
        id=ids.next_serial("exclusion", numbers(book)),
        kind=kind,
        name=name,
        zone=zone.id,
        listed_on=listed_on,
        contact=contact,
        phone=phone,
        buffer_ft=buffer_ft,
        notice_hours=notice_hours,
        note=note,
    )
    book.run(f"INSERT INTO exclusion ({_COLUMNS}) VALUES ({_VALUES})", entry.to_row())
    return entry


def get(book: Book, exclusion_id: str) -> Exclusion:
    """One register entry by id."""
    row = book.one(f"SELECT {_COLUMNS} FROM exclusion WHERE id = ?", (exclusion_id,))
    if row is None:
        raise NotFound("register entry", exclusion_id)
    return Exclusion.from_row(row)


def find(book: Book, kind: str, name: str) -> Exclusion | None:
    """One register entry by kind and name, or nothing."""
    row = book.one(
        f"SELECT {_COLUMNS} FROM exclusion WHERE kind = ? AND name = ?",
        (kind, name),
    )
    return None if row is None else Exclusion.from_row(row)


def all_entries(
    book: Book,
    *,
    zone_id: str | None = None,
    kind: str | None = None,
) -> list[Exclusion]:
    """Every register entry, narrowed if asked."""
    clauses: list[str] = []
    params: list[object] = []
    if zone_id is not None:
        clauses.append("zone = ?")
        params.append(zone_id)
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.all(f"SELECT {_COLUMNS} FROM exclusion{where} ORDER BY id", params)
    return [Exclusion.from_row(row) for row in rows]


def on_register(
    book: Book,
    on: dt.date,
    *,
    zone_id: str | None = None,
) -> list[Exclusion]:
    """Every entry that was on the register on a day."""
    return [one for one in all_entries(book, zone_id=zone_id) if one.on_register(on)]


def absolute(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[Exclusion]:
    """Every entry that no amount of notice gets round."""
    return [one for one in on_register(book, on, zone_id=zone_id) if one.absolute]


def wanting_notice(book: Book, on: dt.date, *, zone_id: str | None = None) -> list[Exclusion]:
    """Every entry that wants telling before a run."""
    return [one for one in on_register(book, on, zone_id=zone_id) if not one.absolute]


def remove(book: Book, exclusion_id: str, on: dt.date, why: str = "") -> Exclusion:
    """Take a place off the register from a day."""
    entry = get(book, exclusion_id)
    if entry.removed_on is not None:
        raise RuleViolation("spray.register", f"{exclusion_id} came off on {entry.removed_on}")
    if on < entry.listed_on:
        raise RuleViolation("spray.register", "an entry cannot come off before it went on")
    note = f"{entry.note}\nremoved: {why}".strip() if why else entry.note
    book.run(
        "UPDATE exclusion SET removed_on = ?, note = ? WHERE id = ?",
        (on.isoformat(), note, exclusion_id),
    )
    return get(book, exclusion_id)


def longest_notice(book: Book, on: dt.date, *, zone_id: str | None = None) -> int:
    """The most notice any entry on the register wants, in hours."""
    wanted = [one.hours for one in wanting_notice(book, on, zone_id=zone_id)]
    return max(wanted) if wanted else 0
