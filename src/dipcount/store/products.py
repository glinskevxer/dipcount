"""Reading and writing the product shelf and the label rates on it."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from dipcount import habitat as hb
from dipcount import ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.product import Label, Product
from dipcount.store.book import Book, Row
from dipcount.units import Quantity, Rate

_PRODUCT = (
    "id, name, registration, maker, active, percent, form, purpose,"
    " restricted, signal, reentry, unit_mass, added_on, withdrawn_on, note"
)
_VALUES = (
    ":id, :name, :registration, :maker, :active, :percent, :form, :purpose,"
    " :restricted, :signal, :reentry, :unit_mass, :added_on, :withdrawn_on, :note"
)
_LABEL = "product, habitat, low_rate, high_rate, per, season_max, interval_days"


def numbers(book: Book) -> list[str]:
    """Every product id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM product")]


def _labels(book: Book, product_id: str) -> tuple[Label, ...]:
    rows = book.all(
        f"SELECT {_LABEL} FROM label_rate WHERE product = ? ORDER BY habitat",
        (product_id,),
    )
    return tuple(Label.from_row(row) for row in rows)


def _load(book: Book, row: Row) -> Product:
    return Product.from_row(row, _labels(book, str(row["id"])))


def add(
    book: Book,
    name: str,
    registration: str,
    maker: str,
    active: str,
    percent: Decimal,
    form: str,
    purpose: str,
    added_on: dt.date,
    *,
    restricted: bool = False,
    signal: str = "caution",
    reentry: int = 0,
    unit_mass: Quantity | None = None,
    note: str = "",
) -> Product:
    """Put a product on the shelf."""
    if find_by_name(book, name) is not None:
        raise Duplicate("product", name)
    if find_by_registration(book, registration) is not None:
        raise Duplicate("registration", registration)
    made = Product(
        id=ids.next_serial("product", numbers(book)),
        name=name,
        registration=registration,
        maker=maker,
        active=active,
        percent=percent,
        form=form,
        purpose=purpose,
        added_on=added_on,
        restricted=restricted,
        signal=signal,
        reentry=reentry,
        unit_mass=unit_mass,
        note=note,
    )
    book.run(f"INSERT INTO product ({_PRODUCT}) VALUES ({_VALUES})", made.to_row())
    return get(book, made.id)


def get(book: Book, product_id: str) -> Product:
    """One product by id, with its label."""
    row = book.one(f"SELECT {_PRODUCT} FROM product WHERE id = ?", (product_id,))
    if row is None:
        raise NotFound("product", product_id)
    return _load(book, row)


def find_by_name(book: Book, name: str) -> Product | None:
    """One product by name, or nothing."""
    row = book.one(f"SELECT {_PRODUCT} FROM product WHERE name = ?", (name,))
    return None if row is None else _load(book, row)


def find_by_registration(book: Book, registration: str) -> Product | None:
    """One product by its registration number, or nothing."""
    row = book.one(f"SELECT {_PRODUCT} FROM product WHERE registration = ?", (registration,))
    return None if row is None else _load(book, row)


def resolve(book: Book, text: str) -> Product:
    """A product by id, by name or by registration number."""
    if ids.looks_like("product", text):
        return get(book, text)
    found = find_by_name(book, text) or find_by_registration(book, text)
    if found is None:
        raise NotFound("product", text)
    return found


def all_products(
    book: Book,
    *,
    purpose: str | None = None,
    form: str | None = None,
    active: str | None = None,
) -> list[Product]:
    """Every product, narrowed if asked."""
    clauses: list[str] = []
    params: list[object] = []
    for column, value in (("purpose", purpose), ("form", form), ("active", active)):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = book.all(f"SELECT {_PRODUCT} FROM product{where} ORDER BY id", params)
    return [_load(book, row) for row in rows]


def on_shelf(book: Book, on: dt.date, *, purpose: str | None = None) -> list[Product]:
    """Every product in use on a day."""
    return [one for one in all_products(book, purpose=purpose) if one.on_shelf(on)]


def withdraw(book: Book, product_id: str, on: dt.date, why: str = "") -> Product:
    """Take a product off the shelf from a day."""
    product = get(book, product_id)
    if product.withdrawn_on is not None:
        raise RuleViolation(
            "product.withdrawn",
            f"{product_id} came off the shelf on {product.withdrawn_on}",
        )
    if on < product.added_on:
        raise RuleViolation(
            "product.withdrawn",
            "a product cannot be withdrawn before it was added",
        )
    note = f"{product.note}\nwithdrawn: {why}".strip() if why else product.note
    book.run(
        "UPDATE product SET withdrawn_on = ?, note = ? WHERE id = ?",
        (on.isoformat(), note, product_id),
    )
    return get(book, product_id)


def label(
    book: Book,
    product_id: str,
    habitat: str,
    low: Rate,
    high: Rate,
    *,
    season_max: Quantity | None = None,
    interval_days: int = 0,
) -> Product:
    """Write one habitat's rate range onto a product's label.

    The habitat has to accept the product's formulation. A granule label for a
    catch basin is not a typing mistake to be caught later, it is a rate that
    could never legally be applied.
    """
    product = get(book, product_id)
    kind = hb.habitat(habitat)
    if not kind.allows(product.form):
        raise RuleViolation(
            "label.form",
            f"a {kind.name} does not take a {product.form}",
        )
    if product.label_for(habitat) is not None:
        raise Duplicate("label", f"{product_id} for {habitat}")
    entry = Label(habitat, low, high, season_max, interval_days)
    book.run(
        f"INSERT INTO label_rate ({_LABEL}) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            product_id,
            entry.habitat,
            str(entry.low.amount),
            str(entry.high.amount),
            entry.per,
            None if entry.season_max is None else str(entry.season_max),
            entry.interval_days,
        ),
    )
    return get(book, product_id)


def for_habitat(
    book: Book,
    habitat: str,
    *,
    purpose: str | None = None,
    on: dt.date | None = None,
) -> list[Product]:
    """Every product whose label covers one kind of water."""
    found = [
        one for one in all_products(book, purpose=purpose) if one.label_for(habitat) is not None
    ]
    if on is not None:
        found = [one for one in found if one.on_shelf(on)]
    return found


def actives(book: Book) -> list[str]:
    """Every active ingredient on the shelf."""
    rows = book.all("SELECT DISTINCT active FROM product ORDER BY active")
    return [str(row["active"]) for row in rows]
