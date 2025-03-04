from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.errors import Duplicate, NotFound
from dipcount.model.inspection import Tally
from dipcount.store import Book, sites, upgrade, zones
from dipcount.store import inspections as store
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    return book


def test_an_inspection_is_numbered_within_its_day(district: Book) -> None:
    first = store.record(district, "SI-0001", clock.moment("2025-06-04 09:00"), "K. Brennaman")
    second = store.record(district, "SI-0002", clock.moment("2025-06-04 11:00"), "K. Brennaman")
    assert first.id == "IN-250604-01"
    assert second.id == "IN-250604-02"


def test_the_next_day_starts_again(district: Book) -> None:
    store.record(district, "SI-0001", clock.moment("2025-06-04 09:00"), "K. Brennaman")
    later = store.record(district, "SI-0001", clock.moment("2025-06-05 09:00"), "K. Brennaman")
    assert later.id == "IN-250605-01"


def test_the_tallies_come_back_with_the_inspection(district: Book) -> None:
    made = store.record(
        district,
        "SI-0001",
        clock.moment("2025-06-04 09:00"),
        "K. Brennaman",
        dips=10,
        tallies=[Tally("CXPP", "2", 24), Tally("CXPP", "P", 6)],
    )
    read = store.get(district, made.id)
    assert read.larvae == 24
    assert read.pupae == 6
    assert read.per_dip == Decimal("2.4")


def test_the_same_species_and_stage_twice_is_refused(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.record(
            district,
            "SI-0001",
            clock.moment("2025-06-04 09:00"),
            "K. Brennaman",
            dips=10,
            tallies=[Tally("CXPP", "2", 24), Tally("CXPP", "2", 6)],
        )
    assert district.count("inspection") == 0


def test_a_refused_inspection_writes_no_tallies(district: Book) -> None:
    with pytest.raises(Exception, match="dry site"):
        store.record(
            district,
            "SI-0001",
            clock.moment("2025-06-04 09:00"),
            "K. Brennaman",
            water=False,
            dips=10,
        )
    assert district.count("larvae") == 0


def test_an_inspection_of_a_site_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.record(district, "SI-0099", clock.moment("2025-06-04 09:00"), "K. Brennaman")


def test_a_missing_inspection(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "IN-250604-01")


def test_inspections_for_a_site_come_back_oldest_first(district: Book) -> None:
    for day in ("2025-06-04", "2025-05-20", "2025-06-18"):
        store.record(district, "SI-0001", clock.moment(f"{day} 09:00"), "K. Brennaman")
    found = store.for_site(district, "SI-0001")
    assert [one.on.isoformat() for one in found] == ["2025-05-20", "2025-06-04", "2025-06-18"]


def test_a_window_narrows_by_local_day(district: Book) -> None:
    for day in ("2025-06-04", "2025-06-10", "2025-06-18"):
        store.record(district, "SI-0001", clock.moment(f"{day} 09:00"), "K. Brennaman")
    found = store.for_site(
        district,
        "SI-0001",
        since=dt.date(2025, 6, 5),
        until=dt.date(2025, 6, 18),
    )
    assert len(found) == 2


def test_a_day_holds_what_happened_on_it_locally(district: Book) -> None:
    store.record(district, "SI-0001", clock.moment("2025-06-04 23:40"), "K. Brennaman")
    store.record(district, "SI-0001", clock.moment("2025-06-05 00:20"), "K. Brennaman")
    assert len(store.on_day(district, dt.date(2025, 6, 4))) == 1


def test_a_reporting_week_holds_seven_days(district: Book) -> None:
    start = clock.week_start(2025, 23)
    for offset in range(9):
        day = start + dt.timedelta(days=offset - 1)
        store.record(district, "SI-0001", clock.moment(f"{day.isoformat()} 09:00"), "K. B")
    assert len(store.in_week(district, 2025, 23)) == 7


def test_the_last_inspection_can_be_asked_for_as_of_a_day(district: Book) -> None:
    for day in ("2025-06-04", "2025-06-10", "2025-06-18"):
        store.record(district, "SI-0001", clock.moment(f"{day} 09:00"), "K. Brennaman")
    assert store.last_seen(district, "SI-0001").on == dt.date(2025, 6, 18)  # type: ignore[union-attr]
    earlier = store.last_seen(district, "SI-0001", on=dt.date(2025, 6, 12))
    assert earlier is not None
    assert earlier.on == dt.date(2025, 6, 10)


def test_a_site_never_inspected_has_nothing(district: Book) -> None:
    assert store.last_seen(district, "SI-0002") is None


def test_only_the_positive_inspections_come_back(district: Book) -> None:
    store.record(district, "SI-0001", clock.moment("2025-06-04 09:00"), "K. B", water=False)
    store.record(
        district,
        "SI-0002",
        clock.moment("2025-06-04 10:00"),
        "K. B",
        dips=10,
        tallies=[Tally("CXPP", "2", 3)],
    )
    found = store.positive_between(district, dt.date(2025, 6, 1), dt.date(2025, 6, 30))
    assert [one.site for one in found] == ["SI-0002"]


def test_the_inspectors_are_listed(district: Book) -> None:
    store.record(district, "SI-0001", clock.moment("2025-06-04 09:00"), "K. Brennaman")
    store.record(district, "SI-0002", clock.moment("2025-06-04 10:00"), "D. Uzoma")
    assert store.inspectors(district) == ["D. Uzoma", "K. Brennaman"]
