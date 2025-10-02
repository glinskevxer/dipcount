from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.block import PHONE
from dipcount.model.exclusion import APIARY, AQUACULTURE, ORGANIC
from dipcount.store import Book, exclusions, upgrade, zones
from dipcount.store import blocks as store

LISTED = dt.date(2025, 4, 1)
GIVEN = clock.moment("2025-07-08 09:00")
FROM = clock.moment("2025-07-10 21:00")
TO = clock.moment("2025-07-11 01:00")


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    store.add(book, "north", "Ardmore east grid", 640.0, LISTED, road_miles=18.4)
    store.add(book, "south", "Weir street grid", 320.0, LISTED, road_miles=11.2)
    exclusions.add(book, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    exclusions.add(book, ORGANIC, "Halloran organics", "north", LISTED)
    return book


def test_a_block_is_numbered_and_found_either_way(district: Book) -> None:
    assert store.get(district, "BK-0001").name == "Ardmore east grid"
    assert store.resolve(district, "Weir street grid").id == "BK-0002"
    with pytest.raises(NotFound):
        store.resolve(district, "Nowhere")


def test_a_block_name_is_not_reused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add(district, "south", "Ardmore east grid", 100.0, LISTED)


def test_blocks_narrow_by_zone(district: Book) -> None:
    assert len(store.all_blocks(district)) == 2
    assert len(store.all_blocks(district, zone_id="ZN-001")) == 1


def test_a_retired_block_leaves_the_run_list(district: Book) -> None:
    store.retire(district, "BK-0001", dt.date(2025, 9, 1), "annexed")
    assert len(store.open_on(district, dt.date(2025, 8, 1))) == 2
    assert len(store.open_on(district, dt.date(2025, 9, 2))) == 1
    assert "annexed" in store.get(district, "BK-0001").note


def test_a_block_is_retired_once(district: Book) -> None:
    store.retire(district, "BK-0001", dt.date(2025, 9, 1))
    with pytest.raises(RuleViolation):
        store.retire(district, "BK-0001", dt.date(2025, 10, 1))


def test_a_register_entry_is_put_inside_a_block(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    assert [one.id for one in store.entries_in(district, "BK-0001", FROM.date())] == ["EX-0001"]
    assert [one.id for one in store.blocks_for(district, "EX-0001")] == ["BK-0001"]


def test_the_same_entry_is_not_linked_twice(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    with pytest.raises(Duplicate):
        store.link(district, "BK-0001", "EX-0001")


def test_one_entry_can_fall_in_two_blocks(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    store.link(district, "BK-0002", "EX-0001")
    assert len(store.blocks_for(district, "EX-0001")) == 2


def test_an_entry_can_be_taken_out_of_a_block(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    store.unlink(district, "BK-0001", "EX-0001")
    assert store.entries_in(district, "BK-0001", FROM.date()) == []
    with pytest.raises(NotFound):
        store.unlink(district, "BK-0001", "EX-0001")


def test_an_entry_off_the_register_drops_out_of_the_block(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    exclusions.remove(district, "EX-0001", dt.date(2025, 6, 1))
    assert store.entries_in(district, "BK-0001", FROM.date()) == []
    assert len(store.entries_in(district, "BK-0001", dt.date(2025, 5, 1))) == 1


def test_a_notice_is_given_over_a_block(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    made = store.give(district, "EX-0001", "BK-0001", GIVEN, FROM, TO, PHONE, "T. Okwuosa")
    assert made.id == "NT-0001"
    assert made.hours_given == 60


def test_a_notice_for_somewhere_outside_the_block_is_refused(district: Book) -> None:
    with pytest.raises(RuleViolation, match="not recorded as falling inside"):
        store.give(district, "EX-0001", "BK-0001", GIVEN, FROM, TO, PHONE, "T. Okwuosa")


def test_notices_narrow_to_one_entry(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    store.link(district, "BK-0001", "EX-0002")
    store.give(district, "EX-0001", "BK-0001", GIVEN, FROM, TO, PHONE, "T. O")
    store.give(district, "EX-0002", "BK-0001", GIVEN, FROM, TO, PHONE, "T. O")
    assert len(store.notices_for(district, "BK-0001")) == 2
    assert len(store.notices_for(district, "BK-0001", exclusion_id="EX-0002")) == 1


def test_the_notice_covering_a_run_is_found(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    store.give(district, "EX-0001", "BK-0001", GIVEN, FROM, TO, PHONE, "T. O")
    inside = store.covering(district, "BK-0001", "EX-0001", clock.moment("2025-07-10 21:30"))
    outside = store.covering(district, "BK-0001", "EX-0001", clock.moment("2025-07-12 21:30"))
    assert inside is not None
    assert outside is None


def test_a_notice_for_another_block_does_not_cover_this_one(district: Book) -> None:
    store.link(district, "BK-0001", "EX-0001")
    store.link(district, "BK-0002", "EX-0001")
    store.give(district, "EX-0001", "BK-0002", GIVEN, FROM, TO, PHONE, "T. O")
    assert store.covering(district, "BK-0001", "EX-0001", FROM) is None


def test_an_absolute_entry_is_still_recorded_in_the_block(district: Book) -> None:
    exclusions.add(district, AQUACULTURE, "Prewitt trout", "north", LISTED, contact="J. P")
    store.link(district, "BK-0001", "EX-0003")
    found = store.entries_in(district, "BK-0001", FROM.date())
    assert [one.absolute for one in found] == [True]


def test_a_missing_block_or_notice(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "BK-0099")
    with pytest.raises(NotFound):
        store.get_notice(district, "NT-0099")
