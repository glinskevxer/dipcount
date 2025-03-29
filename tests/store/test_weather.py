from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.store import Book, upgrade, zones
from dipcount.store import weather as store

OPENED = dt.date(2025, 1, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    store.add_station(book, "Ambrose airport", "north", OPENED, elevation=1043)
    return book


def test_a_station_is_numbered_and_found_either_way(district: Book) -> None:
    assert store.get_station(district, "ST-0001").name == "Ambrose airport"
    assert store.resolve_station(district, "Ambrose airport").id == "ST-0001"
    with pytest.raises(NotFound):
        store.resolve_station(district, "Nowhere")


def test_a_station_name_is_not_reused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add_station(district, "Ambrose airport", "south", OPENED)


def test_stations_narrow_by_zone(district: Book) -> None:
    store.add_station(district, "Pettit levee", "south", OPENED)
    assert len(store.all_stations(district)) == 2
    assert len(store.all_stations(district, zone_id="ZN-002")) == 1


def test_a_reading_is_written_and_read_back(district: Book) -> None:
    made = store.record(district, "ST-0001", dt.date(2025, 6, 4), 84.0, 62.0, rain_in=0.4)
    assert made.id == "WX-250604-01"
    assert store.get(district, made.id).rain_in == 0.4
    assert store.reading(district, "ST-0001", dt.date(2025, 6, 4)) == made


def test_two_readings_from_one_station_on_one_day_is_refused(district: Book) -> None:
    store.record(district, "ST-0001", dt.date(2025, 6, 4), 84.0, 62.0)
    with pytest.raises(Duplicate):
        store.record(district, "ST-0001", dt.date(2025, 6, 4), 85.0, 63.0)


def test_two_stations_on_one_day_are_numbered_apart(district: Book) -> None:
    store.add_station(district, "Pettit levee", "south", OPENED)
    first = store.record(district, "ST-0001", dt.date(2025, 6, 4), 84.0, 62.0)
    second = store.record(district, "ST-0002", dt.date(2025, 6, 4), 83.0, 61.0)
    assert first.id == "WX-250604-01"
    assert second.id == "WX-250604-02"


def test_a_reading_from_a_station_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.record(district, "Nowhere", dt.date(2025, 6, 4), 84.0, 62.0)


def test_a_reading_before_the_station_opened_is_refused(district: Book) -> None:
    with pytest.raises(RuleViolation):
        store.record(district, "ST-0001", dt.date(2024, 6, 4), 84.0, 62.0)


def test_a_closed_station_stops_taking_readings(district: Book) -> None:
    store.close_station(district, "ST-0001", dt.date(2025, 8, 1))
    store.record(district, "ST-0001", dt.date(2025, 7, 4), 84.0, 62.0)
    with pytest.raises(RuleViolation):
        store.record(district, "ST-0001", dt.date(2025, 8, 2), 84.0, 62.0)


def test_a_station_is_not_closed_twice(district: Book) -> None:
    store.close_station(district, "ST-0001", dt.date(2025, 8, 1))
    with pytest.raises(RuleViolation):
        store.close_station(district, "ST-0001", dt.date(2025, 9, 1))


def test_a_station_cannot_close_before_it_opened(district: Book) -> None:
    with pytest.raises(RuleViolation):
        store.close_station(district, "ST-0001", dt.date(2024, 1, 1))


def test_a_series_comes_back_in_day_order(district: Book) -> None:
    for day in (12, 4, 8):
        store.record(district, "ST-0001", dt.date(2025, 6, day), 80.0, 60.0)
    found = store.series(district, "ST-0001", dt.date(2025, 6, 1), dt.date(2025, 6, 30))
    assert [one.on.day for one in found] == [4, 8, 12]


def test_a_series_is_cut_at_both_ends(district: Book) -> None:
    for day in (4, 8, 12):
        store.record(district, "ST-0001", dt.date(2025, 6, day), 80.0, 60.0)
    found = store.series(district, "ST-0001", dt.date(2025, 6, 5), dt.date(2025, 6, 12))
    assert [one.on.day for one in found] == [8, 12]


def test_a_day_gathers_every_station(district: Book) -> None:
    store.add_station(district, "Pettit levee", "south", OPENED)
    store.record(district, "ST-0001", dt.date(2025, 6, 4), 84.0, 62.0)
    store.record(district, "ST-0002", dt.date(2025, 6, 4), 83.0, 61.0)
    assert len(store.on_day(district, dt.date(2025, 6, 4))) == 2


def test_the_gaps_in_a_record_are_named(district: Book) -> None:
    store.record(district, "ST-0001", dt.date(2025, 6, 4), 80.0, 60.0)
    store.record(district, "ST-0001", dt.date(2025, 6, 6), 80.0, 60.0)
    gaps = store.missing_days(district, "ST-0001", dt.date(2025, 6, 4), dt.date(2025, 6, 7))
    assert gaps == [dt.date(2025, 6, 5), dt.date(2025, 6, 7)]


def test_days_before_a_station_opened_are_not_gaps(district: Book) -> None:
    later = store.add_station(district, "Pettit levee", "south", dt.date(2025, 6, 6))
    gaps = store.missing_days(district, later.id, dt.date(2025, 6, 4), dt.date(2025, 6, 7))
    assert gaps == [dt.date(2025, 6, 6), dt.date(2025, 6, 7)]


def test_days_after_a_station_closed_are_not_gaps(district: Book) -> None:
    store.close_station(district, "ST-0001", dt.date(2025, 6, 5))
    gaps = store.missing_days(district, "ST-0001", dt.date(2025, 6, 4), dt.date(2025, 6, 7))
    assert gaps == [dt.date(2025, 6, 4), dt.date(2025, 6, 5)]
