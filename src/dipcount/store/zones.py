"""Reading and writing zones."""

from __future__ import annotations

from dipcount import ids
from dipcount.errors import Duplicate, NotFound
from dipcount.model.zone import Zone
from dipcount.store.book import Book

_COLUMNS = "id, name, supervisor, note"


def add(book: Book, name: str, supervisor: str = "", note: str = "") -> Zone:
    """Put a new zone on the books."""
    if find_by_name(book, name) is not None:
        raise Duplicate("zone", name)
    zone = Zone(ids.next_serial("zone", numbers(book)), name, supervisor, note)
    book.run(
        f"INSERT INTO zone ({_COLUMNS}) VALUES (:id, :name, :supervisor, :note)",
        zone.to_row(),
    )
    return zone


def numbers(book: Book) -> list[str]:
    """Every zone id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM zone")]


def get(book: Book, zone_id: str) -> Zone:
    """One zone by id, refused if it is not there."""
    row = book.one(f"SELECT {_COLUMNS} FROM zone WHERE id = ?", (zone_id,))
    if row is None:
        raise NotFound("zone", zone_id)
    return Zone.from_row(row)


def find_by_name(book: Book, name: str) -> Zone | None:
    """One zone by name, or nothing."""
    row = book.one(f"SELECT {_COLUMNS} FROM zone WHERE name = ?", (name,))
    return None if row is None else Zone.from_row(row)


def resolve(book: Book, text: str) -> Zone:
    """A zone by id or by name, whichever the caller had to hand."""
    if ids.looks_like("zone", text):
        return get(book, text)
    found = find_by_name(book, text)
    if found is None:
        raise NotFound("zone", text)
    return found


def all_zones(book: Book) -> list[Zone]:
    """Every zone, in name order."""
    return [Zone.from_row(row) for row in book.all(f"SELECT {_COLUMNS} FROM zone ORDER BY name")]


def set_supervisor(book: Book, zone_id: str, supervisor: str) -> Zone:
    """Put a different name against a zone."""
    get(book, zone_id)
    book.run("UPDATE zone SET supervisor = ? WHERE id = ?", (supervisor, zone_id))
    return get(book, zone_id)
