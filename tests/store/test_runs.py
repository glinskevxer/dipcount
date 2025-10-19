from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock, formulary
from dipcount.errors import NotFound
from dipcount.store import Book, blocks, inventory, runs, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 4, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    blocks.add(book, "north", "Ardmore east grid", 640.0, LISTED, road_miles=18.4)
    blocks.add(book, "north", "Weir street grid", 320.0, LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Kestrel ULV", "25K-0114", quantity("30 gal"), LISTED)
    inventory.receive(book, "Marrowmist", "25M-0208", quantity("15 gal"), LISTED)
    return book


def go(
    book: Book,
    block: str = "BK-0001",
    lot: str = "LT-0001",
    day: str = "2025-07-10",
    acres: float = 640.0,
    amount: str = "1.4 fl oz",
) -> str:
    made = runs.write(
        book,
        block,
        lot,
        "K. Brennaman",
        clock.moment(f"{day} 21:10"),
        clock.moment(f"{day} 22:40"),
        quantity(amount),
        acres,
        licence="PA-44192",
        wind_mph=4.5,
        temperature=74.0,
        wind_from="SW",
    )
    return made.id


def test_a_run_is_numbered_by_the_night_it_started(district: Book) -> None:
    assert go(district) == "RN-250710-01"
    assert go(district, block="BK-0002", acres=320.0) == "RN-250710-02"


def test_the_product_comes_off_the_lot(district: Book) -> None:
    made = runs.get(district, go(district))
    assert made.product == "PD-0009"
    assert made.licence == "PA-44192"


def test_a_run_over_a_block_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        go(district, block="BK-0099")


def test_a_run_out_of_a_lot_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        go(district, lot="LT-0099")


def test_runs_narrow_by_block_and_product(district: Book) -> None:
    go(district)
    go(district, block="BK-0002", acres=320.0)
    go(district, lot="LT-0002")
    window = (dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert len(runs.between(district, *window)) == 3
    assert len(runs.between(district, *window, block_id="BK-0001")) == 2
    assert len(runs.between(district, *window, product_id="PD-0010")) == 1


def test_a_day_and_a_week_gather_the_runs(district: Book) -> None:
    go(district, day="2025-07-10")
    go(district, day="2025-07-11")
    go(district, day="2025-07-25")
    assert len(runs.on_day(district, dt.date(2025, 7, 10))) == 1
    assert len(runs.in_week(district, 2025, 28)) == 2


def test_runs_over_a_block_come_back_oldest_first(district: Book) -> None:
    go(district, day="2025-07-25")
    go(district, day="2025-07-10")
    found = runs.for_block(district, "BK-0001")
    assert [one.on.day for one in found] == [10, 25]


def test_runs_out_of_a_lot_are_listed(district: Book) -> None:
    go(district)
    go(district, lot="LT-0002")
    assert len(runs.for_lot(district, "LT-0002")) == 1


def test_the_last_run_over_a_block_can_be_asked_as_of_a_day(district: Book) -> None:
    go(district, day="2025-07-10")
    go(district, day="2025-07-25")
    last = runs.last_over(district, "BK-0001")
    assert last is not None
    assert last.on.day == 25
    earlier = runs.last_over(district, "BK-0001", on=dt.date(2025, 7, 20))
    assert earlier is not None
    assert earlier.on.day == 10
    assert runs.last_over(district, "BK-0002") is None


def test_the_season_acres_count_every_pass(district: Book) -> None:
    go(district, day="2025-07-10")
    go(district, day="2025-07-25")
    go(district, day="2025-07-25", acres=320.0)
    assert runs.season_acres(district, "BK-0001", 2025) == 1600.0
    assert runs.season_acres(district, "BK-0001", 2026) == 0.0


def test_the_nights_a_truck_went_out_are_listed(district: Book) -> None:
    go(district, day="2025-07-10")
    go(district, day="2025-07-10", block="BK-0002", acres=320.0)
    go(district, day="2025-07-25")
    found = runs.nights(district, dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert found == [dt.date(2025, 7, 10), dt.date(2025, 7, 25)]


def test_a_run_keeps_the_weather_it_was_made_in(district: Book) -> None:
    made = runs.get(district, go(district))
    assert made.wind_mph == 4.5
    assert made.temperature == 74.0
    assert made.wind_from == "SW"


def test_a_missing_run(district: Book) -> None:
    with pytest.raises(NotFound):
        runs.get(district, "RN-250710-09")
