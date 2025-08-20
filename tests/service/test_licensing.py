from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import formulary
from dipcount.model.applicator import (
    AQUATIC,
    CERTIFIED,
    CORE,
    PUBLIC_HEALTH,
    RIGHT_OF_WAY,
    TECHNICIAN,
)
from dipcount.service import licensing
from dipcount.store import Book, applicators, products, sites, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)
ON = dt.date(2025, 6, 4)
ISSUED = dt.date(2024, 3, 1)
EXPIRES = dt.date(2027, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    sites.add(book, "north", "Kettle bottom", "floodplain", quantity("40 acre"), LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        ISSUED,
        EXPIRES,
    )
    applicators.add(
        book,
        "D. Uzoma",
        "PA-44193",
        TECHNICIAN,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        ISSUED,
        EXPIRES,
        supervisor="AP-001",
    )
    return book


def test_permanent_water_is_aquatic_work_and_a_floodplain_is_not(district: Book) -> None:
    marsh = sites.get(district, "SI-0001")
    flood = sites.get(district, "SI-0002")
    granules = products.resolve(district, "Bactilore G")
    assert licensing.category_for(marsh, granules) == AQUATIC
    assert licensing.category_for(flood, granules) == PUBLIC_HEALTH


def test_adulticiding_is_public_health_wherever_it_happens(district: Book) -> None:
    marsh = sites.get(district, "SI-0001")
    fog = products.resolve(district, "Kestrel ULV")
    assert licensing.category_for(marsh, fog) == PUBLIC_HEALTH


def test_a_licence_without_the_category_does_not_cover_the_site(district: Book) -> None:
    applicators.add(
        district,
        "R. Salcedo",
        "PA-44194",
        CERTIFIED,
        (CORE, RIGHT_OF_WAY),
        ISSUED,
        EXPIRES,
    )
    refused = licensing.check(district, "AP-003", "SI-0001", "Bactilore G", ON)
    assert refused is not None
    assert refused.rule == "licence.category"


def test_the_same_licence_covers_one_site_and_not_the_next(district: Book) -> None:
    applicators.add(
        district,
        "R. Salcedo",
        "PA-44194",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH),
        ISSUED,
        EXPIRES,
    )
    assert not licensing.may_apply(district, "AP-003", "SI-0001", "Bactilore G", ON)
    assert licensing.may_apply(district, "AP-003", "SI-0002", "Bactilore G", ON)


def test_an_expired_licence_is_refused_before_anything_else(district: Book) -> None:
    refused = licensing.check(district, "AP-001", "SI-0001", "Bactilore G", dt.date(2028, 6, 4))
    assert refused is not None
    assert refused.rule == "licence.date"


def test_a_technician_may_apply_what_is_not_restricted(district: Book) -> None:
    assert licensing.may_apply(district, "AP-002", "SI-0001", "Bactilore G", ON)


def test_a_technician_may_not_apply_a_restricted_product(district: Book) -> None:
    refused = licensing.check(district, "AP-002", "SI-0002", "Kestrel ULV", ON)
    assert refused is not None
    assert refused.rule == "licence.grade"
    assert licensing.may_apply(district, "AP-001", "SI-0002", "Kestrel ULV", ON)


def test_the_crew_for_a_job_is_everybody_who_could_make_it(district: Book) -> None:
    both = licensing.crew(district, "SI-0001", "Bactilore G", ON)
    restricted = licensing.crew(district, "SI-0002", "Kestrel ULV", ON)
    assert [one.id for one in both] == ["AP-001", "AP-002"]
    assert [one.id for one in restricted] == ["AP-001"]


def test_somebody_with_no_courses_is_short_of_every_hour(district: Book) -> None:
    found = licensing.standing(district, "AP-001", ON)
    assert found.licensed
    assert found.hours_held == 0
    assert found.hours_short == found.hours_needed
    assert not found.renewable
    assert "hours short" in found.line()


def test_credits_inside_the_cycle_count(district: Book) -> None:
    applicators.credit(district, "AP-001", dt.date(2025, 2, 12), CORE, Decimal(10), "core day")
    applicators.credit(district, "AP-001", dt.date(2026, 2, 12), AQUATIC, Decimal(8), "aquatic day")
    found = licensing.standing(district, "AP-001", ON)
    assert found.hours_held == 18
    assert found.renewable
    assert found.by_category[CORE] == 10
    assert "credits met" in found.line()


def test_a_course_before_the_cycle_opened_does_not_count(district: Book) -> None:
    applicators.credit(district, "AP-001", dt.date(2023, 2, 12), CORE, Decimal(18), "old day")
    found = licensing.standing(district, "AP-001", ON)
    assert found.hours_held == 0


def test_a_technician_needs_fewer_hours(district: Book) -> None:
    applicators.credit(district, "AP-002", dt.date(2025, 2, 12), CORE, Decimal(9), "core day")
    found = licensing.standing(district, "AP-002", ON)
    assert found.renewable
    assert found.hours_needed == 9


def test_being_short_of_credits_does_not_stop_the_work(district: Book) -> None:
    found = licensing.standing(district, "AP-001", ON)
    assert not found.renewable
    assert found.licensed
    assert licensing.may_apply(district, "AP-001", "SI-0001", "Bactilore G", ON)


def test_the_licences_running_out_soon_are_listed(district: Book) -> None:
    soon = licensing.expiring(district, dt.date(2027, 1, 1), days=90)
    assert [one.applicator.id for one in soon] == ["AP-001", "AP-002"]
    assert licensing.expiring(district, ON, days=90) == []


def test_somebody_who_has_left_is_not_on_the_expiry_list(district: Book) -> None:
    applicators.leave(district, "AP-002", dt.date(2026, 8, 1))
    soon = licensing.expiring(district, dt.date(2027, 1, 1), days=90)
    assert [one.applicator.id for one in soon] == ["AP-001"]


def test_everybody_short_of_credits_is_named(district: Book) -> None:
    applicators.credit(district, "AP-001", dt.date(2025, 2, 12), CORE, Decimal(18), "core day")
    short = licensing.short_of_credits(district, ON)
    assert [one.applicator.id for one in short] == ["AP-002"]


def test_the_board_covers_everybody(district: Book) -> None:
    assert [one.applicator.id for one in licensing.board(district, ON)] == ["AP-001", "AP-002"]


def test_the_days_left_count_down(district: Book) -> None:
    found = licensing.standing(district, "AP-001", dt.date(2027, 2, 1))
    assert found.days_left == 28
