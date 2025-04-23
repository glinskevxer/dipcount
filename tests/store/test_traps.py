from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.trap import Catch
from dipcount.store import Book, upgrade, zones
from dipcount.store import traps as store

LISTED = dt.date(2025, 4, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    store.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    store.add(book, "north", "Kettle light 1", "light", LISTED)
    return book


def a_night(book: Book, trap: str = "TR-0001", day: int = 4, **rest: object) -> object:
    return store.record(
        book,
        trap,
        clock.moment(f"2025-06-{day - 1:02d} 16:30"),
        clock.moment(f"2025-06-{day:02d} 08:15"),
        "D. Uzoma",
        **rest,  # type: ignore[arg-type]
    )


def test_traps_are_numbered_and_found_either_way(district: Book) -> None:
    assert store.get(district, "TR-0001").name == "Ambrose gravid 1"
    assert store.resolve(district, "Kettle light 1").id == "TR-0002"
    with pytest.raises(NotFound):
        store.resolve(district, "Nowhere")


def test_a_trap_name_is_not_reused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add(district, "south", "Ambrose gravid 1", "light", LISTED)


def test_traps_narrow_by_zone_and_kind(district: Book) -> None:
    store.add(district, "south", "Rowe bg 1", "bg", LISTED)
    assert len(store.all_traps(district)) == 3
    assert len(store.all_traps(district, zone_id="ZN-001")) == 2
    assert len(store.all_traps(district, kind="gravid")) == 1


def test_a_retired_trap_leaves_the_open_list(district: Book) -> None:
    store.retire(district, "TR-0001", dt.date(2025, 9, 1), "landowner sold")
    assert len(store.open_on(district, dt.date(2025, 8, 1))) == 2
    assert len(store.open_on(district, dt.date(2025, 9, 2))) == 1
    assert "sold" in store.get(district, "TR-0001").note


def test_a_trap_is_not_retired_twice(district: Book) -> None:
    store.retire(district, "TR-0001", dt.date(2025, 9, 1))
    with pytest.raises(RuleViolation):
        store.retire(district, "TR-0001", dt.date(2025, 10, 1))


def test_a_collection_is_numbered_by_the_day_it_came_in(district: Book) -> None:
    first = a_night(district)
    second = a_night(district, trap="TR-0002")
    assert first.id == "CO-250604-01"  # type: ignore[attr-defined]
    assert second.id == "CO-250604-02"  # type: ignore[attr-defined]


def test_the_catches_come_back_with_the_collection(district: Book) -> None:
    made = store.record(
        district,
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        "D. Uzoma",
        catches=[Catch("CXPP", "F", 42), Catch("CXPP", "M", 130)],
    )
    read = store.get_collection(district, made.id)
    assert read.females == 42
    assert read.males == 130
    assert read.index == Decimal("42")


def test_the_same_species_and_sex_twice_is_refused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.record(
            district,
            "TR-0001",
            clock.moment("2025-06-03 16:30"),
            clock.moment("2025-06-04 08:15"),
            "D. Uzoma",
            catches=[Catch("CXPP", "F", 42), Catch("CXPP", "F", 8)],
        )
    assert district.count("collection") == 0


def test_a_refused_collection_writes_no_catches(district: Book) -> None:
    with pytest.raises(Exception, match="did not run"):
        store.record(
            district,
            "TR-0001",
            clock.moment("2025-06-03 16:30"),
            clock.moment("2025-06-04 08:15"),
            "D. Uzoma",
            worked=False,
            catches=[Catch("CXPP", "F", 42)],
        )
    assert district.count("catch") == 0


def test_a_collection_off_a_retired_trap_is_refused(district: Book) -> None:
    store.retire(district, "TR-0001", dt.date(2025, 5, 1))
    with pytest.raises(RuleViolation):
        a_night(district)


def test_a_missing_collection(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get_collection(district, "CO-250604-01")


def test_collections_for_a_trap_come_back_oldest_first(district: Book) -> None:
    for day in (12, 4, 18):
        a_night(district, day=day)
    found = store.for_trap(district, "TR-0001")
    assert [one.on.day for one in found] == [4, 12, 18]


def test_a_window_narrows_by_local_day_and_by_trap(district: Book) -> None:
    a_night(district, day=4)
    a_night(district, trap="TR-0002", day=5)
    a_night(district, day=12)
    assert len(store.between(district, dt.date(2025, 6, 1), dt.date(2025, 6, 30))) == 3
    assert len(store.between(district, dt.date(2025, 6, 5), dt.date(2025, 6, 12))) == 2
    narrowed = store.between(district, dt.date(2025, 6, 1), dt.date(2025, 6, 30), trap_id="TR-0002")
    assert len(narrowed) == 1


def test_a_day_holds_what_came_in_on_it(district: Book) -> None:
    a_night(district, day=4)
    a_night(district, trap="TR-0002", day=5)
    assert len(store.on_day(district, dt.date(2025, 6, 4))) == 1


def test_a_week_gathers_seven_days_of_collections(district: Book) -> None:
    for day in range(1, 9):
        a_night(district, day=day + 1)
    assert len(store.in_week(district, 2025, 23)) == 6


def test_the_last_collection_off_a_trap(district: Book) -> None:
    a_night(district, day=4)
    a_night(district, day=12)
    last = store.last_for_trap(district, "TR-0001")
    assert last is not None
    assert last.on.day == 12
    assert store.last_for_trap(district, "TR-0002") is None
