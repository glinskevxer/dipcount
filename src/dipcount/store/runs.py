"""Reading and writing the runs a truck made."""

from __future__ import annotations

import datetime as dt

from dipcount import clock, ids
from dipcount.errors import NotFound
from dipcount.model.block import Run
from dipcount.store import blocks, inventory, products
from dipcount.store.book import Book
from dipcount.units import Quantity

_COLUMNS = (
    "id, block, product, lot, applicator, licence, started_at, finished_at,"
    " amount, acres, equipment, temperature, wind_mph, wind_from, note"
)
_VALUES = (
    ":id, :block, :product, :lot, :applicator, :licence, :started_at, :finished_at,"
    " :amount, :acres, :equipment, :temperature, :wind_mph, :wind_from, :note"
)


def numbers_on(book: Book, on: dt.date) -> list[str]:
    """Every run id already issued for a day."""
    rows = book.all("SELECT id FROM run WHERE id LIKE ?", (f"RN-{on:%y%m%d}-%",))
    return [str(row["id"]) for row in rows]


def write(
    book: Book,
    block_id: str,
    lot_id: str,
    applicator: str,
    started_at: dt.datetime,
    finished_at: dt.datetime,
    amount: Quantity,
    acres: float,
    *,
    licence: str = "",
    equipment: str = "",
    temperature: float | None = None,
    wind_mph: float | None = None,
    wind_from: str = "",
    note: str = "",
) -> Run:
    """Write one run into the book.

    Nothing here checks the weather or the register. That is the service's
    work, because the check needs the block's entries and the notices given
    over them, and this layer holds neither.
    """
    block = blocks.resolve(book, block_id)
    lot = inventory.get(book, lot_id)
    products.get(book, lot.product)
    on = clock.in_zone(started_at).date()
    made = Run(
        id=ids.next_dated("run", on, numbers_on(book, on)),
        block=block.id,
        product=lot.product,
        lot=lot.id,
        applicator=applicator,
        started_at=started_at,
        finished_at=finished_at,
        amount=amount,
        acres=acres,
        licence=licence,
        equipment=equipment,
        temperature=temperature,
        wind_mph=wind_mph,
        wind_from=wind_from,
        note=note,
    )
    book.run(f"INSERT INTO run ({_COLUMNS}) VALUES ({_VALUES})", made.to_row())
    return get(book, made.id)


def get(book: Book, run_id: str) -> Run:
    """One run by id."""
    row = book.one(f"SELECT {_COLUMNS} FROM run WHERE id = ?", (run_id,))
    if row is None:
        raise NotFound("run", run_id)
    return Run.from_row(row)


def between(
    book: Book,
    start: dt.date,
    end: dt.date,
    *,
    block_id: str | None = None,
    product_id: str | None = None,
) -> list[Run]:
    """Every run started over a run of local days, narrowed if asked."""
    first = clock.to_utc(clock.moment(f"{start.isoformat()} 00:00")).isoformat()
    after = clock.to_utc(
        clock.moment(f"{(end + dt.timedelta(days=1)).isoformat()} 00:00"),
    ).isoformat()
    clauses = ["started_at >= ?", "started_at < ?"]
    params: list[object] = [first, after]
    if block_id is not None:
        clauses.append("block = ?")
        params.append(block_id)
    if product_id is not None:
        clauses.append("product = ?")
        params.append(product_id)
    rows = book.all(
        f"SELECT {_COLUMNS} FROM run WHERE {' AND '.join(clauses)} ORDER BY started_at, id",
        params,
    )
    return [Run.from_row(row) for row in rows]


def on_day(book: Book, on: dt.date) -> list[Run]:
    """Every run started on one local day."""
    return between(book, on, on)


def in_week(book: Book, year: int, week: int) -> list[Run]:
    """Every run started in one reporting week."""
    return between(book, clock.week_start(year, week), clock.week_end(year, week))


def for_block(book: Book, block_id: str) -> list[Run]:
    """Every run over one block, oldest first."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM run WHERE block = ? ORDER BY started_at, id",
        (block_id,),
    )
    return [Run.from_row(row) for row in rows]


def for_lot(book: Book, lot_id: str) -> list[Run]:
    """Every run that came out of one lot."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM run WHERE lot = ? ORDER BY started_at, id",
        (lot_id,),
    )
    return [Run.from_row(row) for row in rows]


def last_over(book: Book, block_id: str, *, on: dt.date | None = None) -> Run | None:
    """The most recent run over a block, up to a day if one is given."""
    found = for_block(book, block_id)
    if on is not None:
        found = [one for one in found if one.on <= on]
    return found[-1] if found else None


def season_acres(book: Book, block_id: str, year: int) -> float:
    """How many acres of a block were fogged in a season, counting repeats."""
    return sum(
        one.acres
        for one in between(book, dt.date(year, 1, 1), dt.date(year, 12, 31), block_id=block_id)
    )


def nights(book: Book, start: dt.date, end: dt.date) -> list[dt.date]:
    """Every local day a run was started on, over a window."""
    seen = {one.on for one in between(book, start, end)}
    return sorted(seen)
