"""Reading and writing treatments."""

from __future__ import annotations

import datetime as dt

from dipcount import clock
from dipcount.errors import NotFound
from dipcount.model.treatment import Treatment
from dipcount.store import inventory, numbering, products, sites, window
from dipcount.store.book import Book
from dipcount.units import Quantity

_COLUMNS = (
    "id, site, product, lot, at, applicator, licence, extent, amount, equipment, inspection, note"
)
_VALUES = (
    ":id, :site, :product, :lot, :at, :applicator, :licence, :extent, :amount,"
    " :equipment, :inspection, :note"
)


def write(
    book: Book,
    site_id: str,
    lot_id: str,
    at: dt.datetime,
    applicator: str,
    extent: Quantity,
    amount: Quantity,
    *,
    licence: str = "",
    equipment: str = "",
    inspection: str | None = None,
    note: str = "",
) -> Treatment:
    """Write one application into the book.

    Nothing here checks a label. That is the service's work, because the check
    needs the site's habitat and the season's history and this layer holds
    neither.
    """
    site = sites.get(book, site_id)
    lot = inventory.get(book, lot_id)
    products.get(book, lot.product)
    on = clock.in_zone(at).date()
    made = Treatment(
        id=numbering.next_dated(book, "treatment", "treatment", on),
        site=site.id,
        product=lot.product,
        lot=lot.id,
        at=at,
        applicator=applicator,
        licence=licence,
        extent=extent,
        amount=amount,
        equipment=equipment,
        inspection=inspection,
        note=note,
    )
    book.run(f"INSERT INTO treatment ({_COLUMNS}) VALUES ({_VALUES})", made.to_row())
    return get(book, made.id)


def get(book: Book, treatment_id: str) -> Treatment:
    """One treatment by id."""
    row = book.one(f"SELECT {_COLUMNS} FROM treatment WHERE id = ?", (treatment_id,))
    if row is None:
        raise NotFound("treatment", treatment_id)
    return Treatment.from_row(row)


def between(
    book: Book,
    start: dt.date,
    end: dt.date,
    *,
    site_id: str | None = None,
    product_id: str | None = None,
) -> list[Treatment]:
    """Every treatment over a run of local days, narrowed if asked."""
    first, after = window.bounds(start, end)
    clauses = ["at >= ?", "at < ?"]
    params: list[object] = [first, after]
    if site_id is not None:
        clauses.append("site = ?")
        params.append(site_id)
    if product_id is not None:
        clauses.append("product = ?")
        params.append(product_id)
    rows = book.all(
        f"SELECT {_COLUMNS} FROM treatment WHERE {' AND '.join(clauses)} ORDER BY at, id",
        params,
    )
    return [Treatment.from_row(row) for row in rows]


def on_day(book: Book, on: dt.date) -> list[Treatment]:
    """Every treatment made on one local day."""
    return between(book, on, on)


def in_week(book: Book, year: int, week: int) -> list[Treatment]:
    """Every treatment made in one reporting week."""
    return between(book, clock.week_start(year, week), clock.week_end(year, week))


def for_site(book: Book, site_id: str, *, product_id: str | None = None) -> list[Treatment]:
    """Every treatment at one site, oldest first."""
    clauses = ["site = ?"]
    params: list[object] = [site_id]
    if product_id is not None:
        clauses.append("product = ?")
        params.append(product_id)
    rows = book.all(
        f"SELECT {_COLUMNS} FROM treatment WHERE {' AND '.join(clauses)} ORDER BY at, id",
        params,
    )
    return [Treatment.from_row(row) for row in rows]


def for_lot(book: Book, lot_id: str) -> list[Treatment]:
    """Every treatment that came out of one lot."""
    rows = book.all(
        f"SELECT {_COLUMNS} FROM treatment WHERE lot = ? ORDER BY at, id",
        (lot_id,),
    )
    return [Treatment.from_row(row) for row in rows]


def last_at(
    book: Book,
    site_id: str,
    *,
    product_id: str | None = None,
    on: dt.date | None = None,
) -> Treatment | None:
    """The most recent treatment at a site, up to a day if one is given."""
    found = for_site(book, site_id, product_id=product_id)
    if on is not None:
        found = [one for one in found if one.on <= on]
    return found[-1] if found else None


def season_total(
    book: Book,
    site_id: str,
    product_id: str,
    year: int,
    *,
    unit: str | None = None,
) -> Quantity:
    """How much of one product has gone on one site in a calendar season."""
    found = between(
        book,
        dt.date(year, 1, 1),
        dt.date(year, 12, 31),
        site_id=site_id,
        product_id=product_id,
    )
    if not found:
        return Quantity.parse(f"0 {unit}") if unit else Quantity.parse("0 each")
    total = found[0].amount
    for one in found[1:]:
        total = total + one.amount
    return total.to(unit) if unit else total


def applicators(book: Book) -> list[str]:
    """Everybody with a treatment against their name."""
    rows = book.all("SELECT DISTINCT applicator FROM treatment ORDER BY applicator")
    return [str(row["applicator"]) for row in rows]
