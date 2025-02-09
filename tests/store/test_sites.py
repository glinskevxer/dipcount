from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.store import Book, upgrade, zones
from dipcount.store import sites as store
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north", "R. Vandeburg")
    zones.add(book, "south", "T. Okwuosa")
    return book


def test_zones_are_numbered_in_order(district: Book) -> None:
    assert [zone.id for zone in zones.all_zones(district)] == ["ZN-001", "ZN-002"]


def test_a_zone_name_is_not_reused(district: Book) -> None:
    with pytest.raises(Duplicate):
        zones.add(district, "north")


def test_a_zone_resolves_by_id_or_by_name(district: Book) -> None:
    assert zones.resolve(district, "north").id == "ZN-001"
    assert zones.resolve(district, "ZN-001").name == "north"
    with pytest.raises(NotFound):
        zones.resolve(district, "east")


def test_a_supervisor_can_be_changed(district: Book) -> None:
    changed = zones.set_supervisor(district, "ZN-001", "M. Ferraro")
    assert changed.supervisor == "M. Ferraro"


def test_a_site_is_added_under_a_zone_by_name(district: Book) -> None:
    site = store.add(
        district,
        "north",
        "Weller Road basins",
        "catch_basin",
        quantity("14 each"),
        LISTED,
    )
    assert site.id == "SI-0001"
    assert site.zone == "ZN-001"
    assert store.get(district, "SI-0001").name == "Weller Road basins"


def test_two_sites_of_the_same_name_in_one_zone_are_refused(district: Book) -> None:
    store.add(district, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    with pytest.raises(Duplicate):
        store.add(district, "north", "Weller Road", "roadside_ditch", quantity("2 acre"), LISTED)


def test_the_same_name_in_another_zone_is_fine(district: Book) -> None:
    store.add(district, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    other = store.add(district, "south", "Weller Road", "catch_basin", quantity("9 each"), LISTED)
    assert other.id == "SI-0002"


def test_sites_are_narrowed_by_zone_and_habitat(district: Book) -> None:
    store.add(district, "north", "Weller", "catch_basin", quantity("14 each"), LISTED)
    store.add(district, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    store.add(district, "south", "Dunlap basins", "catch_basin", quantity("31 each"), LISTED)
    assert len(store.all_sites(district)) == 3
    assert len(store.all_sites(district, zone_id="ZN-001")) == 2
    assert len(store.all_sites(district, habitat="catch_basin")) == 2
    assert len(store.all_sites(district, zone_id="ZN-002", habitat="catch_basin")) == 1


def test_a_missing_site_is_not_found(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "SI-0099")


def test_a_site_added_under_a_zone_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.add(district, "east", "Nowhere", "catch_basin", quantity("1 each"), LISTED)


def test_retiring_takes_a_site_off_the_open_list(district: Book) -> None:
    store.add(district, "north", "Weller", "catch_basin", quantity("14 each"), LISTED)
    store.retire(district, "SI-0001", dt.date(2025, 8, 1), "basins were rebuilt")
    assert store.open_on(district, dt.date(2025, 7, 1))
    assert not store.open_on(district, dt.date(2025, 8, 2))
    assert "rebuilt" in store.get(district, "SI-0001").note


def test_a_site_is_not_retired_twice(district: Book) -> None:
    store.add(district, "north", "Weller", "catch_basin", quantity("14 each"), LISTED)
    store.retire(district, "SI-0001", dt.date(2025, 8, 1))
    with pytest.raises(RuleViolation):
        store.retire(district, "SI-0001", dt.date(2025, 9, 1))


def test_retiring_before_listing_is_refused(district: Book) -> None:
    store.add(district, "north", "Weller", "catch_basin", quantity("14 each"), LISTED)
    with pytest.raises(RuleViolation):
        store.retire(district, "SI-0001", dt.date(2025, 1, 1))


def test_remeasuring_keeps_the_habitat_unit(district: Book) -> None:
    store.add(district, "north", "Weller", "catch_basin", quantity("14 each"), LISTED)
    changed = store.remeasure(district, "SI-0001", quantity("18 each"))
    assert changed.extent == quantity("18 each")
    with pytest.raises(RuleViolation):
        store.remeasure(district, "SI-0001", quantity("2 acre"))


def test_total_extent_adds_a_habitat_up(district: Book) -> None:
    store.add(district, "north", "Sawyer", "cattail_marsh", quantity("6 acre"), LISTED)
    store.add(district, "south", "Pettit", "cattail_marsh", quantity("2.5 acre"), LISTED)
    assert store.total_extent(district, "cattail_marsh") == quantity("8.5 acre")


def test_total_extent_of_nothing_is_zero_in_the_right_unit(district: Book) -> None:
    assert store.total_extent(district, "catch_basin") == quantity("0 each")
    assert store.total_extent(district, "cattail_marsh") == quantity("0 acre")


def test_a_site_round_trips_through_the_book(district: Book) -> None:
    made = store.add(
        district,
        "north",
        "Sawyer marsh",
        "cattail_marsh",
        quantity("6.5 acre"),
        LISTED,
        access="gate off the county road, key 40",
        latitude=41.8781,
        longitude=-93.0977,
        note="cattails right to the edge",
    )
    read = store.get(district, made.id)
    assert read == made
