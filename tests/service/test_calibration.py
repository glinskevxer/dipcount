from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import formulary
from dipcount.model.equipment import FOGGER, SPREADER
from dipcount.service import calibration
from dipcount.store import Book, equipment, sites, upgrade, zones
from dipcount.units import quantity, rate

ADDED = dt.date(2024, 5, 1)
ON = dt.date(2025, 6, 12)
LATER = dt.date(2025, 7, 20)


@pytest.fixture
def shop(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), ADDED)
    formulary.stock(book, dt.date(2025, 1, 15))
    equipment.add(
        book,
        FOGGER,
        "Larkspur",
        "XLR-40",
        "40-11872",
        ADDED,
        nominal=quantity("1.5 fl oz"),
        swath_ft=300.0,
    )
    equipment.add(
        book,
        SPREADER,
        "Hallam",
        "G-6",
        "G6-2201",
        ADDED,
        nominal=quantity("40 lb"),
    )
    return book


def calibrate(book: Book, **rest: object) -> None:
    fields: dict[str, object] = {
        "droplet": 17.0,
        "speed_mph": 10.0,
    }
    fields.update(rest)
    equipment.calibrate(
        book,
        str(fields.pop("equipment_id", "EQ-001")),
        fields.pop("on", ON),  # type: ignore[arg-type]
        "K. Brennaman",
        fields.pop("flow", quantity("1.5 fl oz")),  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )


def test_a_machine_never_calibrated_is_not_usable(shop: Book) -> None:
    found = calibration.standing(shop, "EQ-001", ON)
    assert not found.usable
    assert not found.calibrated
    assert found.refusals()[0].rule == "equipment.calibration"
    assert "never calibrated" in found.line()


def test_a_fresh_calibration_makes_the_machine_usable(shop: Book) -> None:
    calibrate(shop)
    found = calibration.standing(shop, "EQ-001", ON)
    assert found.usable
    assert found.due_on == dt.date(2025, 7, 12)
    assert "usable" in found.line()


def test_a_calibration_runs_out_after_a_month(shop: Book) -> None:
    calibrate(shop)
    found = calibration.standing(shop, "EQ-001", LATER)
    assert not found.usable
    assert found.days_over == 8
    assert found.refusals()[0].rule == "equipment.calibration"


def test_a_flow_outside_tolerance_holds_the_machine(shop: Book) -> None:
    calibrate(shop, flow=quantity("1.9 fl oz"))
    found = calibration.standing(shop, "EQ-001", ON)
    assert not found.usable
    assert not found.flow_ok
    assert any(one.rule == "equipment.flow" for one in found.refusals())


def test_a_coarse_droplet_holds_the_fogger(shop: Book) -> None:
    calibrate(shop, droplet=42.0)
    found = calibration.standing(shop, "EQ-001", ON)
    assert not found.usable
    assert not found.droplet_ok


def test_a_missing_droplet_reading_holds_the_fogger(shop: Book) -> None:
    calibrate(shop, droplet=None)
    assert not calibration.standing(shop, "EQ-001", ON).usable


def test_a_spreader_has_no_droplet_to_read(shop: Book) -> None:
    calibrate(shop, equipment_id="EQ-002", flow=quantity("40 lb"), droplet=None)
    found = calibration.standing(shop, "EQ-002", ON)
    assert found.usable
    assert found.droplet_ok


def test_a_retired_machine_is_held_however_good_the_calibration(shop: Book) -> None:
    calibrate(shop)
    equipment.retire(shop, "EQ-001", dt.date(2025, 6, 20))
    found = calibration.standing(shop, "EQ-001", dt.date(2025, 6, 25))
    assert not found.usable
    assert found.refusals()[0].rule == "equipment.retired"


def test_the_first_refusal_is_what_the_check_returns(shop: Book) -> None:
    assert calibration.check(shop, "EQ-001", ON) is not None
    calibrate(shop)
    assert calibration.check(shop, "EQ-001", ON) is None


def test_only_the_usable_machines_come_back(shop: Book) -> None:
    calibrate(shop)
    found = calibration.usable(shop, ON)
    assert [one.id for one in found] == ["EQ-001"]
    assert calibration.usable(shop, ON, kind=SPREADER) == []


def test_what_is_due_is_listed_most_overdue_first(shop: Book) -> None:
    calibrate(shop)
    waiting = calibration.due(shop, ON)
    assert [one.machine.id for one in waiting] == ["EQ-002"]
    later = calibration.due(shop, LATER)
    assert [one.machine.id for one in later] == ["EQ-002", "EQ-001"]


def test_a_window_brings_the_nearly_due_forward(shop: Book) -> None:
    calibrate(shop)
    calibrate(shop, equipment_id="EQ-002", flow=quantity("40 lb"), droplet=None)
    assert calibration.due(shop, ON) == []
    soon = calibration.due(shop, dt.date(2025, 7, 1), within=14)
    assert len(soon) == 2


def test_the_board_covers_every_machine(shop: Book) -> None:
    assert [one.machine.id for one in calibration.board(shop, ON)] == ["EQ-001", "EQ-002"]


def test_the_target_speed_comes_off_the_measured_flow(shop: Book) -> None:
    calibrate(shop)
    wanted = rate("0.0033 fl oz/acre")
    found = calibration.target_speed(shop, "EQ-001", wanted, ON)
    assert found is not None
    assert found > 0


def test_a_faster_machine_is_driven_faster_for_the_same_rate(shop: Book) -> None:
    calibrate(shop)
    slow = calibration.target_speed(shop, "EQ-001", rate("0.01 fl oz/acre"), ON)
    calibrate(shop, on=dt.date(2025, 6, 13), flow=quantity("1.65 fl oz"))
    fast = calibration.target_speed(shop, "EQ-001", rate("0.01 fl oz/acre"), dt.date(2025, 6, 13))
    assert slow is not None
    assert fast is not None
    assert fast > slow


def test_a_machine_never_calibrated_gives_no_speed(shop: Book) -> None:
    assert calibration.target_speed(shop, "EQ-001", rate("0.01 fl oz/acre"), ON) is None


def test_the_label_middle_and_the_speed_come_back_together(shop: Book) -> None:
    calibrate(shop, equipment_id="EQ-002", flow=quantity("40 lb"), droplet=None, swath_ft=30.0)
    found = calibration.speed_for_label(shop, "EQ-002", "SI-0001", "Bactilore G", ON)
    assert found is not None
    wanted, speed = found
    assert wanted.amount == quantity("6.25 lb")
    assert speed > 0


def test_a_product_not_labelled_for_the_site_gives_nothing(shop: Book) -> None:
    calibrate(shop, equipment_id="EQ-002", flow=quantity("40 lb"), droplet=None, swath_ft=30.0)
    assert calibration.speed_for_label(shop, "EQ-002", "SI-0001", "Kestrel ULV", ON) is None


def test_a_machine_with_no_swath_gives_no_speed(shop: Book) -> None:
    equipment.add(shop, SPREADER, "Hallam", "G-2", "G2-0001", ADDED)
    calibrate(shop, equipment_id="EQ-003", flow=quantity("40 lb"), droplet=None, swath_ft=0.0)
    assert calibration.target_speed(shop, "EQ-003", rate("6 lb/acre"), ON) is None


def test_a_machine_with_no_rating_passes_the_flow_check(shop: Book) -> None:
    equipment.add(shop, SPREADER, "Hallam", "G-2", "G2-0001", ADDED, swath_ft=30.0)
    calibrate(shop, equipment_id="EQ-003", flow=quantity("40 lb"), droplet=None)
    found = calibration.standing(shop, "EQ-003", ON)
    assert found.flow_ok
    assert found.usable


def test_the_days_over_are_nothing_before_the_due_day(shop: Book) -> None:
    calibrate(shop)
    assert calibration.standing(shop, "EQ-001", ON).days_over == 0
    assert calibration.standing(shop, "EQ-001", dt.date(2025, 7, 12)).days_over == 0
    assert calibration.standing(shop, "EQ-001", dt.date(2025, 7, 13)).days_over == 1


def test_the_measured_rate_is_what_the_calibration_says(shop: Book) -> None:
    calibrate(shop)
    found = calibration.standing(shop, "EQ-001", ON)
    assert found.last is not None
    measured = found.last.rate()
    assert measured is not None
    assert measured.amount.amount > Decimal(0)
