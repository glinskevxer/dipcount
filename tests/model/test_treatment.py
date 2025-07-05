from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.model.treatment import Treatment
from dipcount.units import quantity, rate

AT = clock.moment("2025-06-04 10:40")


def a_treatment(**changes: object) -> Treatment:
    fields: dict[str, object] = {
        "id": "TX-250604-01",
        "site": "SI-0001",
        "product": "PD-0001",
        "lot": "LT-0001",
        "at": AT,
        "applicator": "K. Brennaman",
        "extent": quantity("6 acre"),
        "amount": quantity("36 lb"),
    }
    fields.update(changes)
    return Treatment(**fields)  # type: ignore[arg-type]


def test_the_rate_is_worked_out_and_not_stored() -> None:
    made = a_treatment()
    assert made.rate == rate("6 lb/acre")
    assert "rate" not in made.to_row()


def test_a_structure_treatment_gives_a_per_structure_rate() -> None:
    made = a_treatment(extent=quantity("14 each"), amount=quantity("14 each"))
    assert made.rate.per == "each"
    assert made.rate.amount == quantity("1 each")


def test_the_id_has_to_carry_the_day_it_was_made() -> None:
    with pytest.raises(UsageError, match="does not carry"):
        a_treatment(at=clock.moment("2025-06-05 10:40"))


def test_a_treatment_over_nothing_or_of_nothing_is_refused() -> None:
    with pytest.raises(UsageError):
        a_treatment(extent=quantity("0 acre"))
    with pytest.raises(UsageError):
        a_treatment(amount=quantity("0 lb"))


def test_a_treatment_needs_an_applicator_and_a_zone() -> None:
    with pytest.raises(UsageError):
        a_treatment(applicator=" ")
    with pytest.raises(UsageError):
        a_treatment(at=AT.replace(tzinfo=None))


def test_the_references_have_to_be_the_right_kind_of_id() -> None:
    with pytest.raises(UsageError):
        a_treatment(site="TR-0001")
    with pytest.raises(UsageError):
        a_treatment(lot="PD-0001")
    with pytest.raises(UsageError):
        a_treatment(inspection="SI-0001")


def test_an_inspection_can_be_named_or_left_out() -> None:
    assert a_treatment().inspection is None
    assert a_treatment(inspection="IN-250604-01").inspection == "IN-250604-01"


def test_the_active_comes_off_the_share() -> None:
    assert a_treatment().active(Decimal("4.5")) == quantity("1.62 lb")


def test_the_day_and_week_come_off_the_moment() -> None:
    made = a_treatment()
    assert made.on == dt.date(2025, 6, 4)
    assert made.week == "2025-W23"


def test_the_line_reads_like_a_use_report_row() -> None:
    line = a_treatment().line()
    assert "36 lb over 6 acre" in line
    assert "6 lb/acre" in line
    assert "K. Brennaman" in line


def test_the_row_stores_utc() -> None:
    assert str(a_treatment().to_row()["at"]).endswith("+00:00")
