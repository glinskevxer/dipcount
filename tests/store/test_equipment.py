from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.equipment import FOGGER, SPREADER
from dipcount.store import Book, upgrade
from dipcount.store import equipment as store
from dipcount.units import quantity

ADDED = dt.date(2024, 5, 1)
ON = dt.date(2025, 6, 12)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    store.add(
        book,
        FOGGER,
        "Larkspur",
        "XLR-40",
        "40-11872",
        ADDED,
        nominal=quantity("1.5 fl oz"),
        swath_ft=300.0,
    )
    store.add(book, SPREADER, "Hallam", "G-6", "G6-2201", ADDED, nominal=quantity("40 lb"))
    return book


def test_a_machine_is_numbered_and_found_either_way(district: Book) -> None:
    assert store.get(district, "EQ-001").model == "XLR-40"
    assert store.resolve(district, "G6-2201").id == "EQ-002"
    with pytest.raises(NotFound):
        store.resolve(district, "nothing")


def test_a_serial_number_is_used_once(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add(district, FOGGER, "Larkspur", "XLR-40", "40-11872", ADDED)


def test_machines_narrow_by_kind(district: Book) -> None:
    assert len(store.all_machines(district)) == 2
    assert len(store.all_machines(district, kind=FOGGER)) == 1


def test_a_retired_machine_leaves_service(district: Book) -> None:
    store.retire(district, "EQ-001", dt.date(2025, 9, 1), "pump seized")
    assert len(store.in_service(district, ON)) == 2
    assert len(store.in_service(district, dt.date(2025, 9, 2))) == 1
    assert "seized" in store.get(district, "EQ-001").note


def test_a_machine_is_retired_once(district: Book) -> None:
    store.retire(district, "EQ-001", dt.date(2025, 9, 1))
    with pytest.raises(RuleViolation):
        store.retire(district, "EQ-001", dt.date(2025, 10, 1))


def test_a_machine_cannot_be_retired_before_it_arrived(district: Book) -> None:
    with pytest.raises(RuleViolation):
        store.retire(district, "EQ-001", dt.date(2024, 1, 1))


def test_a_calibration_takes_the_machine_swath_when_none_is_given(district: Book) -> None:
    made = store.calibrate(
        district,
        "EQ-001",
        ON,
        "K. Brennaman",
        quantity("1.5 fl oz"),
        droplet=17.0,
        speed_mph=10.0,
    )
    assert made.id == "CA-250612-01"
    assert made.swath_ft == 300.0
    assert made.rate() is not None


def test_a_calibration_can_override_the_swath(district: Book) -> None:
    made = store.calibrate(
        district,
        "EQ-001",
        ON,
        "K. B",
        quantity("1.5 fl oz"),
        swath_ft=150.0,
        speed_mph=10.0,
    )
    assert made.swath_ft == 150.0


def test_two_calibrations_on_one_day_are_numbered_apart(district: Book) -> None:
    store.calibrate(district, "EQ-001", ON, "K. B", quantity("1.5 fl oz"))
    second = store.calibrate(district, "EQ-002", ON, "K. B", quantity("40 lb"))
    assert second.id == "CA-250612-02"


def test_a_calibration_of_a_retired_machine_is_refused(district: Book) -> None:
    store.retire(district, "EQ-001", dt.date(2025, 5, 1))
    with pytest.raises(RuleViolation, match="not in service"):
        store.calibrate(district, "EQ-001", ON, "K. B", quantity("1.5 fl oz"))


def test_calibrations_come_back_oldest_first(district: Book) -> None:
    for day in (12, 3, 20):
        store.calibrate(
            district,
            "EQ-001",
            dt.date(2025, 6, day),
            "K. B",
            quantity("1.5 fl oz"),
        )
    found = store.calibrations_for(district, "EQ-001")
    assert [one.on.day for one in found] == [3, 12, 20]


def test_calibrations_narrow_to_a_window(district: Book) -> None:
    for day in (3, 20):
        store.calibrate(
            district,
            "EQ-001",
            dt.date(2025, 6, day),
            "K. B",
            quantity("1.5 fl oz"),
        )
    found = store.calibrations_for(district, "EQ-001", since=dt.date(2025, 6, 10))
    assert [one.on.day for one in found] == [20]


def test_the_last_calibration_can_be_asked_as_of_a_day(district: Book) -> None:
    for day in (3, 20):
        store.calibrate(
            district,
            "EQ-001",
            dt.date(2025, 6, day),
            "K. B",
            quantity("1.5 fl oz"),
        )
    last = store.last_calibration(district, "EQ-001")
    assert last is not None
    assert last.on.day == 20
    earlier = store.last_calibration(district, "EQ-001", on=dt.date(2025, 6, 10))
    assert earlier is not None
    assert earlier.on.day == 3


def test_a_machine_never_calibrated_has_nothing(district: Book) -> None:
    assert store.last_calibration(district, "EQ-002") is None


def test_a_missing_machine_or_calibration(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "EQ-099")
    with pytest.raises(NotFound):
        store.get_calibration(district, "CA-250612-09")
