from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import UsageError
from dipcount.model.applicator import (
    AQUATIC,
    CERTIFIED,
    CORE,
    PUBLIC_HEALTH,
    RIGHT_OF_WAY,
    TECHNICIAN,
    TRAINEE,
    Applicator,
    Credit,
)

ISSUED = dt.date(2024, 3, 1)
EXPIRES = dt.date(2027, 3, 1)


def an_applicator(**changes: object) -> Applicator:
    fields: dict[str, object] = {
        "id": "AP-001",
        "name": "K. Brennaman",
        "licence": "PA-44192",
        "grade": CERTIFIED,
        "categories": (CORE, PUBLIC_HEALTH),
        "certified_on": ISSUED,
        "expires_on": EXPIRES,
    }
    fields.update(changes)
    return Applicator(**fields)  # type: ignore[arg-type]


def test_a_licence_needs_a_name_a_number_and_a_category() -> None:
    with pytest.raises(UsageError):
        an_applicator(name=" ")
    with pytest.raises(UsageError):
        an_applicator(licence="")
    with pytest.raises(UsageError):
        an_applicator(categories=())


def test_an_unknown_grade_or_category_is_refused() -> None:
    with pytest.raises(UsageError):
        an_applicator(grade="expert")
    with pytest.raises(UsageError):
        an_applicator(categories=(CORE, "livestock"))


def test_a_licence_cannot_expire_before_it_was_issued() -> None:
    with pytest.raises(UsageError):
        an_applicator(expires_on=ISSUED)


def test_a_technician_works_under_somebody() -> None:
    with pytest.raises(UsageError, match="works under"):
        an_applicator(grade=TECHNICIAN)
    assert an_applicator(grade=TECHNICIAN, supervisor="AP-001").supervisor == "AP-001"


def test_a_certified_applicator_works_under_nobody() -> None:
    with pytest.raises(UsageError, match="does not work under"):
        an_applicator(supervisor="AP-002")


def test_a_licence_is_in_date_between_its_two_days() -> None:
    holder = an_applicator()
    assert not holder.licensed(dt.date(2024, 2, 29))
    assert holder.licensed(ISSUED)
    assert holder.licensed(EXPIRES)
    assert not holder.licensed(dt.date(2027, 3, 2))


def test_somebody_who_has_left_stops_being_licensed_here() -> None:
    holder = an_applicator(left_on=dt.date(2025, 8, 1))
    assert holder.licensed(dt.date(2025, 7, 1))
    assert not holder.licensed(dt.date(2025, 8, 2))


def test_the_categories_are_what_the_licence_covers() -> None:
    holder = an_applicator()
    assert holder.covers(PUBLIC_HEALTH)
    assert not holder.covers(RIGHT_OF_WAY)


def test_a_restricted_product_needs_a_certified_applicator() -> None:
    boss = an_applicator()
    hand = an_applicator(
        id="AP-002",
        name="D. Uzoma",
        licence="PA-44193",
        grade=TECHNICIAN,
        supervisor="AP-001",
    )
    on = dt.date(2025, 6, 4)
    assert boss.may_apply(on, PUBLIC_HEALTH, restricted=True)
    assert not hand.may_apply(on, PUBLIC_HEALTH, restricted=True)
    assert hand.may_apply(on, PUBLIC_HEALTH, restricted=False)


def test_a_trainee_applies_nothing_on_their_own() -> None:
    trainee = an_applicator(
        id="AP-003",
        name="R. Salcedo",
        licence="PA-44194",
        grade=TRAINEE,
        supervisor="AP-001",
    )
    on = dt.date(2025, 6, 4)
    assert not trainee.may_apply(on, PUBLIC_HEALTH, restricted=False)
    assert not trainee.may_apply(on, PUBLIC_HEALTH, restricted=True)


def test_a_licence_in_the_wrong_category_covers_nothing_here() -> None:
    holder = an_applicator(categories=(CORE, RIGHT_OF_WAY))
    assert not holder.may_apply(dt.date(2025, 6, 4), PUBLIC_HEALTH, restricted=False)
    assert holder.may_apply(dt.date(2025, 6, 4), RIGHT_OF_WAY, restricted=False)


def test_an_expired_licence_applies_nothing(  # even in the right category
) -> None:
    holder = an_applicator()
    assert not holder.may_apply(dt.date(2028, 6, 4), PUBLIC_HEALTH, restricted=False)


def test_the_hours_a_grade_needs_go_down_the_grades() -> None:
    boss = an_applicator()
    hand = an_applicator(
        id="AP-002", name="D. U", licence="x", grade=TECHNICIAN, supervisor="AP-001"
    )
    assert boss.hours_needed > hand.hours_needed


def test_the_cycle_opens_three_years_before_it_expires() -> None:
    assert an_applicator().cycle_start() == dt.date(2024, 3, 1)


def test_a_credit_needs_hours_a_course_and_a_real_category() -> None:
    with pytest.raises(UsageError):
        Credit(1, "AP-001", ISSUED, CORE, Decimal(0), "core review")
    with pytest.raises(UsageError):
        Credit(1, "AP-001", ISSUED, CORE, Decimal(2), " ")
    with pytest.raises(UsageError):
        Credit(1, "AP-001", ISSUED, "livestock", Decimal(2), "core review")
    assert Credit(1, "AP-001", ISSUED, AQUATIC, Decimal(2), "aquatic day").hours == 2
