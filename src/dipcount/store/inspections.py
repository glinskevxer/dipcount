"""Reading and writing inspections and the tallies under them."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from dipcount import clock
from dipcount.errors import Duplicate, NotFound
from dipcount.model.inspection import Inspection, Tally
from dipcount.store import numbering, sites, window
from dipcount.store.book import Book, Row

_COLUMNS = "id, site, at, inspector, water, dips, note"


def _tallies(book: Book, inspection_id: str) -> tuple[Tally, ...]:
    rows = book.all(
        "SELECT species, stage, tally FROM larvae WHERE inspection = ? ORDER BY species, stage",
        (inspection_id,),
    )
    return tuple(Tally.from_row(row) for row in rows)


def _load(book: Book, row: Row) -> Inspection:
    return Inspection.from_row(row, _tallies(book, str(row["id"])))


def record(
    book: Book,
    site_id: str,
    at: dt.datetime,
    inspector: str,
    *,
    water: bool = True,
    dips: int = 0,
    tallies: Iterable[Tally] = (),
    note: str = "",
) -> Inspection:
    """Write one inspection and everything counted on it."""
    sites.get(book, site_id)
    on = clock.in_zone(at).date()
    lines = tuple(tallies)
    seen = {(one.species, one.stage) for one in lines}
    if len(seen) != len(lines):
        raise Duplicate("tally", "one species and stage counted twice")
    inspection = Inspection(
        id=numbering.next_dated(book, "inspection", "inspection", on),
        site=site_id,
        at=at,
        inspector=inspector,
        water=water,
        dips=dips,
        note=note,
        tallies=lines,
    )
    with book.writing():
        book.run(
            f"INSERT INTO inspection ({_COLUMNS})"
            " VALUES (:id, :site, :at, :inspector, :water, :dips, :note)",
            inspection.to_row(),
        )
        book.run_many(
            "INSERT INTO larvae (inspection, species, stage, tally) VALUES (?, ?, ?, ?)",
            [(inspection.id, one.species, one.stage, one.tally) for one in lines],
        )
    return get(book, inspection.id)


def get(book: Book, inspection_id: str) -> Inspection:
    """One inspection by id, with its tallies."""
    row = book.one(f"SELECT {_COLUMNS} FROM inspection WHERE id = ?", (inspection_id,))
    if row is None:
        raise NotFound("inspection", inspection_id)
    return _load(book, row)


def for_site(
    book: Book,
    site_id: str,
    *,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> list[Inspection]:
    """Every inspection of one site, oldest first."""
    clauses = ["site = ?"]
    params: list[object] = [site_id]
    if since is not None:
        clauses.append("at >= ?")
        params.append(window.bounds(since, since)[0])
    if until is not None:
        clauses.append("at < ?")
        params.append(window.bounds(until, until)[1])
    rows = book.all(
        f"SELECT {_COLUMNS} FROM inspection WHERE {' AND '.join(clauses)} ORDER BY at",
        params,
    )
    return [_load(book, row) for row in rows]


def between(book: Book, start: dt.date, end: dt.date) -> list[Inspection]:
    """Every inspection over a run of local days, both ends included."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM inspection WHERE at >= ? AND at < ? ORDER BY at",
        window.bounds(start, end),
    )
    return [_load(book, row) for row in rows]


def on_day(book: Book, on: dt.date) -> list[Inspection]:
    """Every inspection made on one local day."""
    return between(book, on, on)


def in_week(book: Book, year: int, week: int) -> list[Inspection]:
    """Every inspection made in one reporting week."""
    return between(book, clock.week_start(year, week), clock.week_end(year, week))


def last_seen(book: Book, site_id: str, on: dt.date | None = None) -> Inspection | None:
    """The most recent inspection of a site, up to a day if one is given."""
    found = for_site(book, site_id, until=on)
    return found[-1] if found else None


def positive_between(book: Book, start: dt.date, end: dt.date) -> list[Inspection]:
    """Every inspection over a run of days that found something."""
    return [one for one in between(book, start, end) if one.positive]


def inspectors(book: Book) -> list[str]:
    """Everybody who has an inspection against their name."""
    rows = book.all("SELECT DISTINCT inspector FROM inspection ORDER BY inspector")
    return [str(row["inspector"]) for row in rows]
