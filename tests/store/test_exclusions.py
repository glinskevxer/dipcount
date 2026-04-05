from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.exclusion import APIARY, AQUACULTURE, ORGANIC
from dipcount.store import Book, upgrade, zones
from dipcount.store import exclusions as store

LISTED = dt.date(2025, 3, 1)
ON = dt.date(2025, 7, 10)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    store.add(book, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    store.add(book, ORGANIC, "Halloran organics", "south", LISTED, contact="B. Halloran")
    return book


def test_an_entry_is_numbered_and_found(district: Book) -> None:
    assert store.get(district, "EX-0001").name == "Ferrand apiary"
    found = store.find(district, APIARY, "Ferrand apiary")
    assert found is not None
    assert found.id == "EX-0001"


def test_the_same_kind_and_name_twice_is_refused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")


def test_the_same_name_under_another_kind_is_fine(district: Book) -> None:
    made = store.add(district, ORGANIC, "Ferrand apiary", "north", LISTED)
    assert made.id == "EX-0003"


def test_entries_narrow_by_zone_and_kind(district: Book) -> None:
    assert len(store.all_entries(district)) == 2
    assert len(store.all_entries(district, zone_id="ZN-001")) == 1
    assert len(store.all_entries(district, kind=ORGANIC)) == 1


def test_an_entry_under_a_zone_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.add(district, APIARY, "Nowhere", "east", LISTED, contact="x")


def test_only_the_current_entries_are_on_the_register(district: Book) -> None:
    store.remove(district, "EX-0001", dt.date(2025, 6, 1), "hives moved")
    assert len(store.on_register(district, dt.date(2025, 5, 1))) == 2
    assert len(store.on_register(district, ON)) == 1
    assert "hives moved" in store.get(district, "EX-0001").note


def test_an_entry_comes_off_once(district: Book) -> None:
    store.remove(district, "EX-0001", dt.date(2025, 6, 1))
    with pytest.raises(RuleViolation):
        store.remove(district, "EX-0001", dt.date(2025, 7, 1))


def test_an_entry_cannot_come_off_before_it_went_on(district: Book) -> None:
    with pytest.raises(RuleViolation):
        store.remove(district, "EX-0001", dt.date(2024, 1, 1))


def test_the_absolute_entries_are_kept_apart(district: Book) -> None:
    store.add(district, AQUACULTURE, "Prewitt trout", "north", LISTED, contact="J. Prewitt")
    assert [one.id for one in store.absolute(district, ON)] == ["EX-0003"]
    assert [one.id for one in store.wanting_notice(district, ON)] == ["EX-0001", "EX-0002"]


def test_the_longest_notice_is_the_one_the_run_has_to_meet(district: Book) -> None:
    assert store.longest_notice(district, ON) == 48
    assert store.longest_notice(district, ON, zone_id="ZN-002") == 24


def test_a_register_with_nothing_on_it_wants_no_notice(book: Book) -> None:
    upgrade(book)
    zones.add(book, "north")
    assert store.longest_notice(book, ON) == 0


def test_an_absolute_entry_is_not_counted_in_the_notice(district: Book) -> None:
    store.add(district, AQUACULTURE, "Prewitt trout", "north", LISTED, contact="J. P")
    assert store.longest_notice(district, ON, zone_id="ZN-001") == 48


def test_an_entry_that_wants_more_than_its_kind(district: Book) -> None:
    made = store.add(
        district, APIARY, "Kellams bees", "north", LISTED, contact="P. K", notice_hours=72
    )
    assert made.hours == 72
    assert store.longest_notice(district, ON) == 72


def test_an_entry_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "EX-0099")
