"""Reading and writing pools and the results that come back on them."""

from __future__ import annotations

import datetime as dt

from dipcount import clock, species
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.pool import PENDING, Assay, Pool
from dipcount.store import numbering, traps
from dipcount.store.book import Book, Row

_POOL = "id, collection, species, size, submitted_on, lab, note"
_ASSAY = "pool, virus, outcome, tested_on, ct"


def _assays(book: Book, pool_id: str) -> tuple[Assay, ...]:
    rows = book.all(
        f"SELECT {_ASSAY} FROM assay WHERE pool = ? ORDER BY virus",
        (pool_id,),
    )
    return tuple(Assay.from_row(row) for row in rows)


def _load(book: Book, row: Row) -> Pool:
    return Pool.from_row(row, _assays(book, str(row["id"])))


def pooled(book: Book, collection_id: str, code: str) -> int:
    """How many of one species out of one jar have already gone to the lab."""
    found = book.value(
        "SELECT sum(size) FROM pool WHERE collection = ? AND species = ?",
        (collection_id, code),
    )
    return int(found or 0)


def submit(
    book: Book,
    collection_id: str,
    code: str,
    size: int,
    submitted_on: dt.date,
    *,
    lab: str = "",
    note: str = "",
) -> Pool:
    """Send one vial of one species out of one jar to the laboratory.

    The jar is the limit. Pools of a species out of one collection cannot add
    up to more females than were counted in it, because there is nowhere else
    they could have come from.
    """
    collection = traps.get_collection(book, collection_id)
    species.species(code)
    caught = collection.females_of(code)
    already = pooled(book, collection_id, code)
    if size + already > caught:
        raise RuleViolation(
            "pool.jar",
            f"{collection_id} held {caught} female {code}"
            f" and {already} are already pooled, so {size} more is too many",
        )
    made = Pool(
        id=numbering.next_dated(book, "pool", "pool", submitted_on),
        collection=collection.id,
        species=code,
        size=size,
        submitted_on=submitted_on,
        lab=lab,
        note=note,
    )
    book.run(
        f"INSERT INTO pool ({_POOL})"
        " VALUES (:id, :collection, :species, :size, :submitted_on, :lab, :note)",
        made.to_row(),
    )
    return get(book, made.id)


def get(book: Book, pool_id: str) -> Pool:
    """One pool by id, with whatever has come back on it."""
    row = book.one(f"SELECT {_POOL} FROM pool WHERE id = ?", (pool_id,))
    if row is None:
        raise NotFound("pool", pool_id)
    return _load(book, row)


def report(
    book: Book,
    pool_id: str,
    virus: str,
    outcome: str,
    tested_on: dt.date | None = None,
    ct: float | None = None,
) -> Pool:
    """Write one virus result against one pool."""
    pool = get(book, pool_id)
    if pool.result(virus) is not None:
        raise Duplicate("result", f"{pool_id} for {virus}")
    assay = Assay(virus, outcome, tested_on, ct)
    book.run(
        f"INSERT INTO assay ({_ASSAY}) VALUES (?, ?, ?, ?, ?)",
        (
            pool_id,
            assay.virus,
            assay.outcome,
            None if assay.tested_on is None else assay.tested_on.isoformat(),
            assay.ct,
        ),
    )
    return get(book, pool_id)


def for_collection(book: Book, collection_id: str) -> list[Pool]:
    """Every pool made out of one jar."""
    rows = book.all(
        f"SELECT {_POOL} FROM pool WHERE collection = ? ORDER BY id",
        (collection_id,),
    )
    return [_load(book, row) for row in rows]


def submitted_between(book: Book, start: dt.date, end: dt.date) -> list[Pool]:
    """Every pool sent to the laboratory over a run of days."""
    rows = book.all(
        f"SELECT {_POOL} FROM pool WHERE submitted_on >= ? AND submitted_on <= ?"
        " ORDER BY submitted_on, id",
        (start.isoformat(), end.isoformat()),
    )
    return [_load(book, row) for row in rows]


def in_week(book: Book, year: int, week: int) -> list[Pool]:
    """Every pool submitted in one reporting week."""
    return submitted_between(book, clock.week_start(year, week), clock.week_end(year, week))


def outstanding(book: Book, virus: str) -> list[Pool]:
    """Every pool with nothing back yet for one virus."""
    return [
        one
        for one in submitted_between(book, dt.date(1900, 1, 1), dt.date(2999, 12, 31))
        if one.outcome(virus) == PENDING
    ]


def positive_between(book: Book, virus: str, start: dt.date, end: dt.date) -> list[Pool]:
    """Every pool that came back positive for a virus, by submission day."""
    return [one for one in submitted_between(book, start, end) if one.is_positive(virus)]


def labs(book: Book) -> list[str]:
    """Every laboratory the district has sent something to."""
    rows = book.all("SELECT DISTINCT lab FROM pool WHERE lab <> '' ORDER BY lab")
    return [str(row["lab"]) for row in rows]
