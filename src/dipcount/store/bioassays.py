"""Reading and writing bottle bioassays."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from dipcount.errors import Duplicate, NotFound
from dipcount.model.bioassay import Bioassay, Reading
from dipcount.store import numbering, zones
from dipcount.store.book import Book, Row

_ASSAY = "id, active, species, source, zone, on_day, tested_by, dose_ug, diagnostic, note"
_VALUES = (
    ":id, :active, :species, :source, :zone, :on_day, :tested_by, :dose_ug, :diagnostic, :note"
)
_BOTTLE = "bioassay, label, minute, knocked, total"


def _readings(book: Book, assay_id: str) -> tuple[Reading, ...]:
    rows = book.all(
        f"SELECT {_BOTTLE} FROM bottle WHERE bioassay = ? ORDER BY minute, label",
        (assay_id,),
    )
    return tuple(Reading.from_row(row) for row in rows)


def _load(book: Book, row: Row) -> Bioassay:
    return Bioassay.from_row(row, _readings(book, str(row["id"])))


def start(
    book: Book,
    active: str,
    code: str,
    source: str,
    on: dt.date,
    tested_by: str,
    dose_ug: float,
    diagnostic: int,
    *,
    zone_id: str | None = None,
    readings: Iterable[Reading] = (),
    note: str = "",
) -> Bioassay:
    """Write one assay and whatever has been read off it so far."""
    zone = None if zone_id is None else zones.resolve(book, zone_id).id
    lines = tuple(readings)
    if len({(one.label, one.minute) for one in lines}) != len(lines):
        raise Duplicate("reading", "one bottle read twice at one minute")
    made = Bioassay(
        id=numbering.next_dated(book, "bioassay", "bioassay", on),
        active=active,
        species=code,
        source=source,
        on=on,
        tested_by=tested_by,
        dose_ug=dose_ug,
        diagnostic=diagnostic,
        zone=zone,
        note=note,
        readings=lines,
    )
    with book.writing():
        book.run(f"INSERT INTO bioassay ({_ASSAY}) VALUES ({_VALUES})", made.to_row())
        book.run_many(
            f"INSERT INTO bottle ({_BOTTLE}) VALUES (?, ?, ?, ?, ?)",
            [(made.id, one.label, one.minute, one.knocked, one.total) for one in lines],
        )
    return get(book, made.id)


def read(
    book: Book,
    assay_id: str,
    label: str,
    minute: int,
    knocked: int,
    total: int,
) -> Bioassay:
    """Write one more bottle reading onto an assay."""
    assay = get(book, assay_id)
    if any(one.label == label and one.minute == minute for one in assay.readings):
        raise Duplicate("reading", f"{label} at {minute} minutes on {assay_id}")
    entry = Reading(label, minute, knocked, total)
    book.run(
        f"INSERT INTO bottle ({_BOTTLE}) VALUES (?, ?, ?, ?, ?)",
        (assay_id, entry.label, entry.minute, entry.knocked, entry.total),
    )
    return get(book, assay_id)


def get(book: Book, assay_id: str) -> Bioassay:
    """One assay by id, with its readings."""
    row = book.one(f"SELECT {_ASSAY} FROM bioassay WHERE id = ?", (assay_id,))
    if row is None:
        raise NotFound("bioassay", assay_id)
    return _load(book, row)


def all_assays(
    book: Book,
    *,
    active: str | None = None,
    code: str | None = None,
    zone_id: str | None = None,
    source: str | None = None,
) -> list[Bioassay]:
    """Every assay, narrowed if asked, oldest first."""
    clauses: list[str] = []
    params: list[object] = []
    for column, value in (
        ("active", active),
        ("species", code),
        ("zone", zone_id),
        ("source", source),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.all(f"SELECT {_ASSAY} FROM bioassay{where} ORDER BY on_day, id", params)
    return [_load(book, row) for row in rows]


def between(book: Book, start_day: dt.date, end_day: dt.date) -> list[Bioassay]:
    """Every assay run over a window."""
    rows = book.all(
        f"SELECT {_ASSAY} FROM bioassay WHERE on_day >= ? AND on_day <= ? ORDER BY on_day, id",
        (start_day.isoformat(), end_day.isoformat()),
    )
    return [_load(book, row) for row in rows]


def latest(
    book: Book,
    active: str,
    code: str,
    *,
    zone_id: str | None = None,
    on: dt.date | None = None,
) -> Bioassay | None:
    """The most recent assay of one active against one species."""
    found = all_assays(book, active=active, code=code, zone_id=zone_id)
    if on is not None:
        found = [one for one in found if one.on <= on]
    return found[-1] if found else None


def actives(book: Book) -> list[str]:
    """Every active ingredient anything has been assayed against."""
    rows = book.all("SELECT DISTINCT active FROM bioassay ORDER BY active")
    return [str(row["active"]) for row in rows]
