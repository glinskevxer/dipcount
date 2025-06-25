from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.model.lot import APPLIED, CORRECTION, Draw, Lot, Stock
from dipcount.units import quantity

RECEIVED = dt.date(2025, 3, 3)
AT = clock.moment("2025-06-04 09:15")


def a_lot(**changes: object) -> Lot:
    fields: dict[str, object] = {
        "id": "LT-0001",
        "product": "PD-0001",
        "code": "24G-1187",
        "received_on": RECEIVED,
        "quantity": quantity("400 lb"),
    }
    fields.update(changes)
    return Lot(**fields)  # type: ignore[arg-type]


def a_draw(**changes: object) -> Draw:
    fields: dict[str, object] = {
        "seq": 1,
        "lot": "LT-0001",
        "at": AT,
        "amount": quantity("30 lb"),
        "reason": APPLIED,
        "actor": "K. Brennaman",
    }
    fields.update(changes)
    return Draw(**fields)  # type: ignore[arg-type]


def test_a_lot_needs_the_code_off_the_container() -> None:
    with pytest.raises(UsageError):
        a_lot(code=" ")


def test_a_lot_of_nothing_is_not_a_lot() -> None:
    with pytest.raises(UsageError):
        a_lot(quantity=quantity("0 lb"))


def test_a_lot_cannot_expire_before_it_arrived() -> None:
    with pytest.raises(UsageError):
        a_lot(expires_on=RECEIVED - dt.timedelta(days=1))


def test_a_lot_with_no_date_never_expires() -> None:
    assert not a_lot().expired(dt.date(2030, 1, 1))
    assert not a_lot().expires_within(dt.date(2030, 1, 1), 30)


def test_a_lot_expires_the_day_after_its_date() -> None:
    lot = a_lot(expires_on=dt.date(2026, 3, 31))
    assert not lot.expired(dt.date(2026, 3, 31))
    assert lot.expired(dt.date(2026, 4, 1))


def test_a_lot_going_out_of_date_soon_is_flagged() -> None:
    lot = a_lot(expires_on=dt.date(2025, 7, 1))
    assert lot.expires_within(dt.date(2025, 6, 4), 30)
    assert not lot.expires_within(dt.date(2025, 6, 4), 10)
    assert not lot.expires_within(dt.date(2025, 7, 2), 30)


def test_a_draw_needs_a_real_reason_and_a_name() -> None:
    with pytest.raises(UsageError):
        a_draw(reason="borrowed")
    with pytest.raises(UsageError):
        a_draw(actor="  ")


def test_a_draw_of_nothing_is_not_a_draw() -> None:
    with pytest.raises(UsageError):
        a_draw(amount=quantity("0 lb"))


def test_only_a_correction_can_put_product_back() -> None:
    with pytest.raises(UsageError, match="correction"):
        a_draw(amount=quantity("-5 lb"))
    assert a_draw(amount=quantity("-5 lb"), reason=CORRECTION).amount.amount < 0


def test_a_draw_needs_a_moment_with_a_zone() -> None:
    with pytest.raises(UsageError):
        a_draw(at=AT.replace(tzinfo=None))


def test_the_draw_day_is_local() -> None:
    assert a_draw().on == dt.date(2025, 6, 4)


def test_stock_is_what_came_in_less_what_went_out() -> None:
    stock = Stock(a_lot(), quantity("120 lb"), draws=4)
    assert stock.left == quantity("280 lb")
    assert not stock.empty
    assert stock.can_take(quantity("280 lb"))
    assert not stock.can_take(quantity("281 lb"))


def test_an_empty_lot_is_empty() -> None:
    assert Stock(a_lot(), quantity("400 lb")).empty


def test_a_correction_puts_stock_back() -> None:
    assert Stock(a_lot(), quantity("-10 lb")).left == quantity("410 lb")


def test_the_stock_line_reads_like_a_shelf_card() -> None:
    line = Stock(a_lot(), quantity("120 lb"), draws=4).line()
    assert "24G-1187" in line
    assert "280 lb left of 400 lb" in line
