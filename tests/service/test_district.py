from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.service import district
from dipcount.store import Book, upgrade
from dipcount.store import audit as trail
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)
BOSS = "R. Vandeburg"


@pytest.fixture
def book_with_zones(book: Book) -> Book:
    upgrade(book)
    district.list_zone(book, BOSS, "north", "R. Vandeburg")
    district.list_zone(book, BOSS, "south", "T. Okwuosa")
    return book


def a_site(book: Book, name: str = "Weller Road basins") -> str:
    return district.list_site(
        book,
        BOSS,
        "north",
        name,
        "catch_basin",
        quantity("14 each"),
        LISTED,
    ).id


def test_opening_a_zone_leaves_a_line(book_with_zones: Book) -> None:
    lines = trail.about(book_with_zones, "ZN-001")
    assert [entry.action for entry in lines] == ["opened zone"]
    assert lines[0].actor == BOSS


def test_listing_a_site_leaves_a_line_naming_the_habitat(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    lines = trail.about(book_with_zones, site_id)
    assert lines[0].action == "listed site"
    assert "catch basin" in lines[0].detail
    assert "14 each" in lines[0].detail


def test_a_refused_site_leaves_nothing_behind(book_with_zones: Book) -> None:
    a_site(book_with_zones)
    with pytest.raises(Duplicate):
        a_site(book_with_zones)
    assert book_with_zones.count("site") == 1
    assert len(trail.walk(book_with_zones)) == 3


def test_a_site_with_the_wrong_extent_unit_writes_nothing(book_with_zones: Book) -> None:
    before = len(trail.walk(book_with_zones))
    with pytest.raises(Exception, match="measured in"):
        district.list_site(
            book_with_zones,
            BOSS,
            "north",
            "Sawyer marsh",
            "cattail_marsh",
            quantity("14 each"),
            LISTED,
        )
    assert book_with_zones.count("site") == 0
    assert len(trail.walk(book_with_zones)) == before


def test_retiring_records_the_reason(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    district.retire_site(book_with_zones, BOSS, site_id, dt.date(2025, 8, 1), "basins rebuilt")
    lines = district.site_history(book_with_zones, site_id)
    assert [entry.action for entry in lines] == ["listed site", "retired site"]
    assert lines[-1].detail == "basins rebuilt"


def test_remeasuring_keeps_what_it_used_to_be(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    district.remeasure_site(book_with_zones, BOSS, site_id, quantity("18 each"))
    lines = district.site_history(book_with_zones, site_id)
    assert lines[-1].detail == "14 each to 18 each"


def test_remeasuring_to_the_same_extent_is_refused(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    with pytest.raises(RuleViolation, match="already measures"):
        district.remeasure_site(book_with_zones, BOSS, site_id, quantity("14 each"))
    assert len(district.site_history(book_with_zones, site_id)) == 1


def test_moving_a_site_between_zones(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    moved = district.move_site(book_with_zones, BOSS, site_id, "south")
    assert moved.zone == "ZN-002"
    assert district.site_history(book_with_zones, site_id)[-1].detail == "ZN-001 to ZN-002"


def test_moving_a_site_into_its_own_zone_is_refused(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    with pytest.raises(RuleViolation, match="already in"):
        district.move_site(book_with_zones, BOSS, site_id, "north")


def test_moving_onto_a_name_already_used_there(book_with_zones: Book) -> None:
    site_id = a_site(book_with_zones)
    district.list_site(
        book_with_zones,
        BOSS,
        "south",
        "Weller Road basins",
        "catch_basin",
        quantity("9 each"),
        LISTED,
    )
    with pytest.raises(Duplicate):
        district.move_site(book_with_zones, BOSS, site_id, "south")
    assert book_with_zones.count("site", "zone = ?", ("ZN-001",)) == 1


def test_history_of_a_site_that_is_not_there(book_with_zones: Book) -> None:
    with pytest.raises(NotFound):
        district.site_history(book_with_zones, "SI-0099")
