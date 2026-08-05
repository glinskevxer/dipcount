from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import UsageError
from dipcount.store import Book, numbering, sites, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    return book


def test_an_empty_table_holds_nothing(district: Book) -> None:
    assert numbering.taken(district, "site") == []
    assert numbering.taken_on(district, "inspection", "inspection", LISTED) == []


def test_the_identifiers_come_back_in_order(district: Book) -> None:
    for name in ("a", "b", "c"):
        sites.add(district, "north", name, "catch_basin", quantity("4 each"), LISTED)
    assert numbering.taken(district, "site") == ["SI-0001", "SI-0002", "SI-0003"]


def test_the_next_serial_follows_what_is_taken(district: Book) -> None:
    assert numbering.next_serial(district, "site", "site") == "SI-0001"
    sites.add(district, "north", "a", "catch_basin", quantity("4 each"), LISTED)
    assert numbering.next_serial(district, "site", "site") == "SI-0002"


def test_the_next_dated_number_starts_again_each_day(district: Book) -> None:
    first = numbering.next_dated(district, "inspection", "inspection", LISTED)
    assert first == "IN-250301-01"
    other = numbering.next_dated(district, "inspection", "inspection", dt.date(2025, 3, 2))
    assert other == "IN-250302-01"


def test_a_dated_listing_takes_only_that_day(district: Book) -> None:
    sites.add(district, "north", "a", "catch_basin", quantity("4 each"), LISTED)
    for number, day in ((1, "250301"), (2, "250301"), (1, "250302")):
        district.run(
            "INSERT INTO inspection (id, site, at, inspector, water, dips, note)"
            " VALUES (?, 'SI-0001', '2025-03-01T00:00:00+00:00', 'K. B', 1, 0, '')",
            (f"IN-{day}-{number:02d}",),
        )
    assert numbering.taken_on(district, "inspection", "inspection", LISTED) == [
        "IN-250301-01",
        "IN-250301-02",
    ]


def test_a_kind_that_carries_no_date_cannot_be_listed_by_one(district: Book) -> None:
    with pytest.raises(UsageError):
        numbering.taken_on(district, "site", "site", LISTED)


def test_a_serial_kind_cannot_be_minted_as_a_dated_one(district: Book) -> None:
    with pytest.raises(UsageError):
        numbering.next_dated(district, "site", "site", LISTED)


def test_a_dated_kind_cannot_be_minted_as_a_serial(district: Book) -> None:
    with pytest.raises(UsageError):
        numbering.next_serial(district, "inspection", "inspection")
