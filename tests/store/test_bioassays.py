from __future__ import annotations

import datetime as dt

import pytest

from dipcount.errors import Duplicate, NotFound
from dipcount.model.bioassay import COLONY, CONTROL, FIELD, RESISTANT, SUSCEPTIBLE, Reading
from dipcount.store import Book, upgrade, zones
from dipcount.store import bioassays as store

ON = dt.date(2025, 8, 12)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    return book


def bottles(knocked: int, total: int = 25, minute: int = 30) -> list[Reading]:
    return [Reading(str(one + 1), minute, knocked, total) for one in range(4)]


def run(book: Book, knocked: int = 25, **rest: object) -> str:
    fields: dict[str, object] = {
        "active": "permethrin",
        "code": "CXPP",
        "source": FIELD,
        "on": ON,
        "zone_id": "north",
    }
    fields.update(rest)
    made = store.start(
        book,
        str(fields["active"]),
        str(fields["code"]),
        str(fields["source"]),
        fields["on"],  # type: ignore[arg-type]
        "K. Brennaman",
        43.0,
        30,
        zone_id=fields["zone_id"],  # type: ignore[arg-type]
        readings=bottles(knocked),
    )
    return made.id


def test_an_assay_is_numbered_by_the_day_it_was_run(district: Book) -> None:
    assert run(district) == "BA-250812-01"
    assert run(district) == "BA-250812-02"


def test_the_readings_come_back_with_the_assay(district: Book) -> None:
    made = store.get(district, run(district, knocked=20))
    assert len(made.readings) == 4
    assert made.verdict() == RESISTANT


def test_one_bottle_is_not_read_twice_at_one_minute(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.start(
            district,
            "permethrin",
            "CXPP",
            FIELD,
            ON,
            "K. B",
            43.0,
            30,
            readings=[Reading("1", 30, 20, 25), Reading("1", 30, 22, 25)],
        )
    assert district.count("bioassay") == 0


def test_a_refused_assay_writes_no_bottles(district: Book) -> None:
    with pytest.raises(Exception, match="species"):
        store.start(district, "permethrin", "ZZZZ", FIELD, ON, "K. B", 43.0, 30)
    assert district.count("bottle") == 0


def test_more_readings_can_be_added_later(district: Book) -> None:
    made = run(district, knocked=23)
    after = store.read(district, made, CONTROL, 30, 2, 25)
    assert after.corrected()
    assert len(after.readings) == 5


def test_the_same_bottle_and_minute_is_refused_on_the_way_in(district: Book) -> None:
    made = run(district)
    store.read(district, made, CONTROL, 30, 0, 25)
    with pytest.raises(Duplicate):
        store.read(district, made, CONTROL, 30, 1, 25)


def test_assays_narrow_four_ways(district: Book) -> None:
    run(district)
    run(district, active="malathion")
    run(district, code="CXTR")
    run(district, zone_id="south")
    run(district, source=COLONY)
    assert len(store.all_assays(district)) == 5
    assert len(store.all_assays(district, active="permethrin")) == 4
    assert len(store.all_assays(district, code="CXTR")) == 1
    assert len(store.all_assays(district, zone_id="ZN-002")) == 1
    assert len(store.all_assays(district, source=COLONY)) == 1


def test_a_window_takes_what_was_run_inside_it(district: Book) -> None:
    run(district)
    run(district, on=dt.date(2025, 9, 3))
    found = store.between(district, dt.date(2025, 8, 1), dt.date(2025, 8, 31))
    assert len(found) == 1


def test_the_latest_assay_is_found_as_of_a_day(district: Book) -> None:
    run(district, knocked=25)
    run(district, knocked=20, on=dt.date(2025, 9, 3))
    last = store.latest(district, "permethrin", "CXPP")
    assert last is not None
    assert last.verdict() == RESISTANT
    earlier = store.latest(district, "permethrin", "CXPP", on=dt.date(2025, 8, 20))
    assert earlier is not None
    assert earlier.verdict() == SUSCEPTIBLE


def test_the_latest_narrows_to_a_zone(district: Book) -> None:
    run(district, knocked=20)
    run(district, knocked=25, zone_id="south")
    north = store.latest(district, "permethrin", "CXPP", zone_id="ZN-001")
    south = store.latest(district, "permethrin", "CXPP", zone_id="ZN-002")
    assert north is not None
    assert south is not None
    assert north.verdict() == RESISTANT
    assert south.verdict() == SUSCEPTIBLE


def test_nothing_assayed_gives_nothing(district: Book) -> None:
    assert store.latest(district, "permethrin", "CXPP") is None
    assert store.actives(district) == []


def test_the_actives_assayed_are_listed(district: Book) -> None:
    run(district)
    run(district, active="malathion")
    assert store.actives(district) == ["malathion", "permethrin"]


def test_an_assay_without_a_zone_is_allowed(district: Book) -> None:
    made = store.start(
        district,
        "permethrin",
        "CXPP",
        COLONY,
        ON,
        "K. B",
        43.0,
        30,
        readings=bottles(25),
    )
    assert made.zone is None


def test_an_assay_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "BA-250812-09")
