from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.applicator import CERTIFIED, CORE, PUBLIC_HEALTH, TECHNICIAN
from dipcount.store import Book, upgrade
from dipcount.store import applicators as store

ISSUED = dt.date(2024, 3, 1)
EXPIRES = dt.date(2027, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    store.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH),
        ISSUED,
        EXPIRES,
    )
    return book


def test_an_applicator_is_numbered_and_found_three_ways(district: Book) -> None:
    assert store.get(district, "AP-001").name == "K. Brennaman"
    assert store.resolve(district, "K. Brennaman").id == "AP-001"
    assert store.resolve(district, "PA-44192").id == "AP-001"
    with pytest.raises(NotFound):
        store.resolve(district, "Nobody")


def test_a_name_and_a_licence_are_each_used_once(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add(district, "K. Brennaman", "PA-9", CERTIFIED, (CORE,), ISSUED, EXPIRES)
    with pytest.raises(Duplicate):
        store.add(district, "Somebody", "PA-44192", CERTIFIED, (CORE,), ISSUED, EXPIRES)


def test_a_technician_is_added_under_a_certified_applicator(district: Book) -> None:
    made = store.add(
        district,
        "D. Uzoma",
        "PA-44193",
        TECHNICIAN,
        (CORE, PUBLIC_HEALTH),
        ISSUED,
        EXPIRES,
        supervisor="AP-001",
    )
    assert made.supervisor == "AP-001"
    assert [one.id for one in store.under(district, "AP-001")] == ["AP-002"]


def test_a_technician_cannot_supervise(district: Book) -> None:
    store.add(
        district,
        "D. Uzoma",
        "PA-44193",
        TECHNICIAN,
        (CORE,),
        ISSUED,
        EXPIRES,
        supervisor="AP-001",
    )
    with pytest.raises(RuleViolation, match="cannot supervise"):
        store.add(
            district,
            "R. Salcedo",
            "PA-44194",
            TECHNICIAN,
            (CORE,),
            ISSUED,
            EXPIRES,
            supervisor="AP-002",
        )


def test_applicators_narrow_by_grade(district: Book) -> None:
    store.add(
        district,
        "D. Uzoma",
        "PA-44193",
        TECHNICIAN,
        (CORE,),
        ISSUED,
        EXPIRES,
        supervisor="AP-001",
    )
    assert len(store.all_applicators(district)) == 2
    assert len(store.all_applicators(district, grade=TECHNICIAN)) == 1


def test_only_the_in_date_licences_are_working(district: Book) -> None:
    assert len(store.working(district, dt.date(2025, 6, 4))) == 1
    assert store.working(district, dt.date(2028, 6, 4)) == []


def test_a_licence_is_renewed_forwards_only(district: Book) -> None:
    after = store.renew(district, "AP-001", dt.date(2027, 3, 1), dt.date(2030, 3, 1))
    assert after.expires_on == dt.date(2030, 3, 1)
    with pytest.raises(RuleViolation, match="already licensed"):
        store.renew(district, "AP-001", ISSUED, EXPIRES)


def test_somebody_who_leaves_stops_working(district: Book) -> None:
    store.leave(district, "AP-001", dt.date(2025, 8, 1))
    assert store.working(district, dt.date(2025, 9, 1)) == []
    with pytest.raises(RuleViolation):
        store.leave(district, "AP-001", dt.date(2025, 9, 1))


def test_a_credit_is_recorded_against_a_licence(district: Book) -> None:
    made = store.credit(
        district,
        "AP-001",
        dt.date(2025, 2, 12),
        CORE,
        Decimal("3"),
        "core review day",
    )
    assert made.hours == 3
    assert len(store.credits_for(district, "AP-001")) == 1


def test_the_same_course_on_the_same_day_twice(district: Book) -> None:
    store.credit(district, "AP-001", dt.date(2025, 2, 12), CORE, Decimal(3), "core review day")
    with pytest.raises(Duplicate):
        store.credit(district, "AP-001", dt.date(2025, 2, 12), CORE, Decimal(3), "core review day")


def test_the_same_course_in_another_year_is_fine(district: Book) -> None:
    store.credit(district, "AP-001", dt.date(2025, 2, 12), CORE, Decimal(3), "core review day")
    store.credit(district, "AP-001", dt.date(2026, 2, 12), CORE, Decimal(3), "core review day")
    assert len(store.credits_for(district, "AP-001")) == 2


def test_credits_narrow_to_a_window(district: Book) -> None:
    store.credit(district, "AP-001", dt.date(2024, 2, 12), CORE, Decimal(3), "one")
    store.credit(district, "AP-001", dt.date(2025, 2, 12), CORE, Decimal(3), "two")
    found = store.credits_for(district, "AP-001", since=dt.date(2025, 1, 1))
    assert [one.course for one in found] == ["two"]


def test_a_credit_against_somebody_who_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.credit(district, "AP-009", dt.date(2025, 2, 12), CORE, Decimal(3), "one")
    with pytest.raises(NotFound):
        store.get_credit(district, 99)
