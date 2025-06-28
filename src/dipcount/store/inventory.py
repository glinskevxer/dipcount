"""Reading and writing lots, and every draw made off them."""

from __future__ import annotations

import datetime as dt

from dipcount import clock, ids
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.lot import APPLIED, Draw, Lot, Stock
from dipcount.store import products
from dipcount.store.book import Book
from dipcount.units import Quantity

_LOT = "id, product, code, received_on, quantity, expires_on, held_at, note"
_DRAW = "seq, lot, at, amount, reason, reference, actor"


def numbers(book: Book) -> list[str]:
    """Every lot id already issued."""
    return [str(row["id"]) for row in book.all("SELECT id FROM lot")]


def receive(
    book: Book,
    product_id: str,
    code: str,
    quantity: Quantity,
    received_on: dt.date,
    *,
    expires_on: dt.date | None = None,
    held_at: str = "",
    note: str = "",
) -> Lot:
    """Book a delivery in."""
    product = products.resolve(book, product_id)
    if find_by_code(book, product.id, code) is not None:
        raise Duplicate("lot", f"{product.name} {code}")
    lot = Lot(
        id=ids.next_serial("lot", numbers(book)),
        product=product.id,
        code=code,
        received_on=received_on,
        quantity=quantity,
        expires_on=expires_on,
        held_at=held_at,
        note=note,
    )
    book.run(
        f"INSERT INTO lot ({_LOT}) VALUES"
        " (:id, :product, :code, :received_on, :quantity, :expires_on, :held_at, :note)",
        lot.to_row(),
    )
    return lot


def get(book: Book, lot_id: str) -> Lot:
    """One lot by id."""
    row = book.one(f"SELECT {_LOT} FROM lot WHERE id = ?", (lot_id,))
    if row is None:
        raise NotFound("lot", lot_id)
    return Lot.from_row(row)


def find_by_code(book: Book, product_id: str, code: str) -> Lot | None:
    """One lot by product and manufacturer code, or nothing."""
    row = book.one(
        f"SELECT {_LOT} FROM lot WHERE product = ? AND code = ?",
        (product_id, code),
    )
    return None if row is None else Lot.from_row(row)


def all_lots(book: Book, *, product_id: str | None = None) -> list[Lot]:
    """Every lot, optionally of one product."""
    where = " WHERE product = ?" if product_id else ""
    params = (product_id,) if product_id else ()
    rows = book.all(f"SELECT {_LOT} FROM lot{where} ORDER BY id", params)
    return [Lot.from_row(row) for row in rows]


def draws(book: Book, lot_id: str) -> list[Draw]:
    """Every draw off one lot, oldest first."""
    rows = book.all(f"SELECT {_DRAW} FROM draw WHERE lot = ? ORDER BY seq", (lot_id,))
    return [Draw.from_row(row) for row in rows]


def stock(book: Book, lot_id: str) -> Stock:
    """What is left of a lot, worked out from its draws."""
    lot = get(book, lot_id)
    made = draws(book, lot_id)
    drawn = Quantity(lot.quantity.amount * 0, lot.quantity.unit)
    for one in made:
        drawn = drawn + one.amount
    return Stock(lot=lot, drawn=drawn, draws=len(made))


def draw(
    book: Book,
    lot_id: str,
    amount: Quantity,
    at: dt.datetime,
    actor: str,
    *,
    reason: str = APPLIED,
    reference: str = "",
) -> Draw:
    """Take an amount off a lot.

    The shelf is the limit. A draw that would take more than is there is a
    counting mistake somewhere, and letting it through turns one mistake into
    a stock figure nobody can reconcile.
    """
    holding = stock(book, lot_id)
    if amount.dimension != holding.lot.quantity.dimension:
        raise RuleViolation(
            "stock.unit",
            f"{holding.lot.id} is measured in {holding.lot.quantity.unit}",
        )
    if amount.amount > 0 and not holding.can_take(amount):
        raise RuleViolation(
            "stock.short",
            f"{holding.lot.id} has {holding.left} left and {amount} was asked for",
        )
    made = Draw(
        seq=0,
        lot=holding.lot.id,
        at=at,
        amount=amount,
        reason=reason,
        actor=actor,
        reference=reference,
    )
    cursor = book.run(
        f"INSERT INTO draw ({_DRAW.replace('seq, ', '')}) VALUES (?, ?, ?, ?, ?, ?)",
        (
            made.lot,
            clock.to_utc(made.at).isoformat(),
            str(made.amount),
            made.reason,
            made.reference,
            made.actor,
        ),
    )
    return get_draw(book, int(cursor.lastrowid or 0))


def get_draw(book: Book, seq: int) -> Draw:
    """One draw by its sequence number."""
    row = book.one(f"SELECT {_DRAW} FROM draw WHERE seq = ?", (seq,))
    if row is None:
        raise NotFound("draw", str(seq))
    return Draw.from_row(row)


def for_reference(book: Book, reference: str) -> list[Draw]:
    """Every draw made against one treatment or other record."""
    rows = book.all(f"SELECT {_DRAW} FROM draw WHERE reference = ? ORDER BY seq", (reference,))
    return [Draw.from_row(row) for row in rows]


def holdings(book: Book, *, product_id: str | None = None) -> list[Stock]:
    """What is on the shelf, lot by lot."""
    return [stock(book, one.id) for one in all_lots(book, product_id=product_id)]


def on_hand(book: Book, product_id: str) -> Quantity | None:
    """How much of one product is on the shelf across every lot."""
    found = holdings(book, product_id=product_id)
    if not found:
        return None
    total = found[0].left
    for one in found[1:]:
        total = total + one.left
    return total


def usable(book: Book, product_id: str, on: dt.date) -> list[Stock]:
    """Every lot of a product that is in date and has something left."""
    return [
        one
        for one in holdings(book, product_id=product_id)
        if not one.empty and not one.lot.expired(on)
    ]


def expiring(book: Book, on: dt.date, days: int = 60) -> list[Stock]:
    """Every lot with something left that goes out of date soon."""
    return [one for one in holdings(book) if not one.empty and one.lot.expires_within(on, days)]


def recall(book: Book, product_id: str, code: str) -> list[Draw]:
    """Every draw ever made off one manufacturer code."""
    lot = find_by_code(book, product_id, code)
    if lot is None:
        raise NotFound("lot", f"{product_id} {code}")
    return draws(book, lot.id)
