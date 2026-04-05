from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock, formulary
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.lot import CORRECTION, DISPOSED
from dipcount.store import Book, upgrade
from dipcount.store import inventory as store
from dipcount.units import quantity

RECEIVED = dt.date(2025, 3, 3)
AT = clock.moment("2025-06-04 09:15")


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    formulary.stock(book, dt.date(2025, 1, 15))
    store.receive(
        book,
        "Bactilore G",
        "24G-1187",
        quantity("400 lb"),
        RECEIVED,
        expires_on=dt.date(2026, 3, 31),
        held_at="shop, north rack",
    )
    return book


def test_a_lot_is_numbered_and_found_by_code(district: Book) -> None:
    assert store.get(district, "LT-0001").code == "24G-1187"
    found = store.find_by_code(district, "PD-0001", "24G-1187")
    assert found is not None
    assert found.id == "LT-0001"


def test_the_same_code_twice_for_one_product_is_refused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.receive(district, "Bactilore G", "24G-1187", quantity("40 lb"), RECEIVED)


def test_the_same_code_under_another_product_is_fine(district: Book) -> None:
    made = store.receive(district, "Sphaerix WG", "24G-1187", quantity("40 lb"), RECEIVED)
    assert made.id == "LT-0002"


def test_a_fresh_lot_is_all_there(district: Book) -> None:
    holding = store.stock(district, "LT-0001")
    assert holding.left == quantity("400 lb")
    assert holding.draws == 0


def test_a_draw_comes_off_the_shelf(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("30 lb"), AT, "K. Brennaman")
    holding = store.stock(district, "LT-0001")
    assert holding.left == quantity("370 lb")
    assert holding.draws == 1


def test_the_draws_off_a_lot_add_up(district: Book) -> None:
    for _ in range(4):
        store.draw(district, "LT-0001", quantity("30 lb"), AT, "K. Brennaman")
    assert store.stock(district, "LT-0001").left == quantity("280 lb")


def test_a_draw_bigger_than_the_shelf_is_refused(district: Book) -> None:
    with pytest.raises(RuleViolation, match="left"):
        store.draw(district, "LT-0001", quantity("401 lb"), AT, "K. Brennaman")
    assert store.stock(district, "LT-0001").left == quantity("400 lb")


def test_the_shelf_can_be_emptied_exactly(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("400 lb"), AT, "K. Brennaman")
    assert store.stock(district, "LT-0001").empty


def test_a_draw_in_another_unit_of_the_same_dimension(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("160 oz"), AT, "K. Brennaman")
    assert store.stock(district, "LT-0001").left == quantity("390 lb")


def test_a_draw_in_the_wrong_dimension_is_refused(district: Book) -> None:
    with pytest.raises(RuleViolation, match="measured in"):
        store.draw(district, "LT-0001", quantity("2 gal"), AT, "K. Brennaman")


def test_a_correction_puts_product_back(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("30 lb"), AT, "K. Brennaman")
    store.draw(
        district,
        "LT-0001",
        quantity("-10 lb"),
        AT,
        "K. Brennaman",
        reason=CORRECTION,
    )
    assert store.stock(district, "LT-0001").left == quantity("380 lb")


def test_a_disposal_comes_off_like_anything_else(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("40 lb"), AT, "K. B", reason=DISPOSED)
    assert store.stock(district, "LT-0001").left == quantity("360 lb")


def test_draws_are_found_by_what_they_were_for(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("30 lb"), AT, "K. B", reference="TX-250604-01")
    store.draw(district, "LT-0001", quantity("10 lb"), AT, "K. B", reference="TX-250604-02")
    found = store.for_reference(district, "TX-250604-01")
    assert [str(one.amount) for one in found] == ["30 lb"]


def test_what_is_on_hand_adds_the_lots_up(district: Book) -> None:
    store.receive(district, "Bactilore G", "24G-1204", quantity("200 lb"), RECEIVED)
    store.draw(district, "LT-0001", quantity("50 lb"), AT, "K. B")
    assert store.on_hand(district, "PD-0001") == quantity("550 lb")


def test_a_product_with_no_lots_has_nothing_on_hand(district: Book) -> None:
    assert store.on_hand(district, "PD-0002") is None


def test_an_expired_lot_is_not_usable(district: Book) -> None:
    assert len(store.usable(district, "PD-0001", dt.date(2026, 3, 31))) == 1
    assert store.usable(district, "PD-0001", dt.date(2026, 4, 1)) == []


def test_an_empty_lot_is_not_usable(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("400 lb"), AT, "K. B")
    assert store.usable(district, "PD-0001", RECEIVED) == []


def test_what_is_going_out_of_date_is_named(district: Book) -> None:
    found = store.expiring(district, dt.date(2026, 3, 1), days=60)
    assert [one.lot.id for one in found] == ["LT-0001"]
    assert store.expiring(district, dt.date(2025, 6, 1), days=60) == []


def test_an_emptied_lot_is_not_worth_reporting_as_expiring(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("400 lb"), AT, "K. B")
    assert store.expiring(district, dt.date(2026, 3, 1), days=60) == []


def test_a_recall_names_every_draw_off_the_code(district: Book) -> None:
    store.draw(district, "LT-0001", quantity("30 lb"), AT, "K. B", reference="TX-250604-01")
    store.draw(district, "LT-0001", quantity("20 lb"), AT, "K. B", reference="TX-250605-01")
    found = store.recall(district, "PD-0001", "24G-1187")
    assert [one.reference for one in found] == ["TX-250604-01", "TX-250605-01"]


def test_a_recall_on_a_code_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.recall(district, "PD-0001", "nothing")


def test_a_lot_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "LT-0099")
    with pytest.raises(NotFound):
        store.get_draw(district, 99)
