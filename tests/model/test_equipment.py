from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import UsageError
from dipcount.model.equipment import (
    FOGGER,
    SPREADER,
    Calibration,
    Machine,
    acres_per_hour,
    applied_rate,
    speed_for,
)
from dipcount.units import quantity, rate

ADDED = dt.date(2024, 5, 1)
ON = dt.date(2025, 6, 12)


def a_machine(**changes: object) -> Machine:
    fields: dict[str, object] = {
        "id": "EQ-001",
        "kind": FOGGER,
        "maker": "Larkspur",
        "model": "XLR-40",
        "serial": "40-11872",
        "added_on": ADDED,
        "nominal": quantity("1.5 fl oz"),
        "swath_ft": 300.0,
    }
    fields.update(changes)
    return Machine(**fields)  # type: ignore[arg-type]


def a_calibration(**changes: object) -> Calibration:
    fields: dict[str, object] = {
        "id": "CA-250612-01",
        "equipment": "EQ-001",
        "on": ON,
        "tested_by": "K. Brennaman",
        "flow": quantity("1.5 fl oz"),
        "droplet": 17.0,
        "swath_ft": 300.0,
        "speed_mph": 10.0,
    }
    fields.update(changes)
    return Calibration(**fields)  # type: ignore[arg-type]


def test_ground_covered_is_speed_times_swath() -> None:
    assert acres_per_hour(10.0, 300.0) == Decimal("3000") / Decimal("8.25")
    assert acres_per_hour(5.0, 300.0) * 2 == acres_per_hour(10.0, 300.0)


def test_a_machine_standing_still_covers_nothing() -> None:
    with pytest.raises(UsageError):
        acres_per_hour(0.0, 300.0)
    with pytest.raises(UsageError):
        acres_per_hour(10.0, 0.0)


def test_driving_faster_thins_the_rate_rather_than_thickening_it() -> None:
    slow = applied_rate(quantity("1.5 fl oz"), 5.0, 300.0)
    fast = applied_rate(quantity("1.5 fl oz"), 10.0, 300.0)
    assert fast.amount.amount * 2 == slow.amount.amount


def test_a_wider_swath_thins_the_rate_the_same_way() -> None:
    narrow = applied_rate(quantity("1.5 fl oz"), 10.0, 150.0)
    wide = applied_rate(quantity("1.5 fl oz"), 10.0, 300.0)
    assert wide.amount.amount * 2 == narrow.amount.amount


def test_the_speed_that_hits_a_wanted_rate_is_worked_out() -> None:
    wanted = applied_rate(quantity("1.5 fl oz"), 10.0, 300.0)
    assert speed_for(quantity("1.5 fl oz"), wanted, 300.0) == Decimal(10)


def test_a_slower_machine_has_to_be_driven_faster() -> None:
    wanted = rate("0.5 fl oz/acre")
    fast_flow = speed_for(quantity("3 fl oz"), wanted, 300.0)
    slow_flow = speed_for(quantity("1.5 fl oz"), wanted, 300.0)
    assert fast_flow > slow_flow


def test_a_rate_of_nothing_cannot_be_driven_to() -> None:
    with pytest.raises(UsageError):
        speed_for(quantity("1.5 fl oz"), rate("0 fl oz/acre"), 300.0)
    with pytest.raises(UsageError):
        speed_for(quantity("1.5 fl oz"), rate("1 fl oz/acre"), 0.0)


def test_a_machine_needs_a_serial_a_model_and_a_real_kind() -> None:
    with pytest.raises(UsageError):
        a_machine(serial=" ")
    with pytest.raises(UsageError):
        a_machine(model="")
    with pytest.raises(UsageError):
        a_machine(kind="watering can")


def test_only_the_fogging_machines_carry_the_droplet_ceiling() -> None:
    assert a_machine().is_ulv
    assert not a_machine(kind=SPREADER, nominal=quantity("40 lb")).is_ulv


def test_a_machine_is_in_service_between_its_dates() -> None:
    made = a_machine(retired_on=dt.date(2026, 5, 1))
    assert not made.in_service(dt.date(2024, 4, 1))
    assert made.in_service(ON)
    assert not made.in_service(dt.date(2026, 5, 2))
    with pytest.raises(UsageError):
        a_machine(retired_on=dt.date(2024, 4, 1))


def test_a_calibration_carries_its_own_day_in_its_id() -> None:
    with pytest.raises(UsageError, match="does not carry"):
        a_calibration(on=dt.date(2025, 6, 13))


def test_a_calibration_needs_a_name_and_a_flow() -> None:
    with pytest.raises(UsageError):
        a_calibration(tested_by=" ")
    with pytest.raises(UsageError):
        a_calibration(flow=quantity("0 fl oz"))


def test_the_flow_tolerance_is_ten_percent_both_ways() -> None:
    nominal = quantity("1.5 fl oz")
    assert a_calibration(flow=quantity("1.35 fl oz")).within(nominal)
    assert a_calibration(flow=quantity("1.65 fl oz")).within(nominal)
    assert not a_calibration(flow=quantity("1.3 fl oz")).within(nominal)
    assert not a_calibration(flow=quantity("1.7 fl oz")).within(nominal)


def test_a_fogger_over_the_droplet_ceiling_fails() -> None:
    assert a_calibration(droplet=30.0).droplet_ok(ulv=True)
    assert not a_calibration(droplet=42.0).droplet_ok(ulv=True)
    assert not a_calibration(droplet=None).droplet_ok(ulv=True)


def test_a_spreader_has_no_droplet_to_measure() -> None:
    assert a_calibration(droplet=None).droplet_ok(ulv=False)


def test_a_calibration_without_a_speed_gives_no_rate() -> None:
    assert a_calibration(speed_mph=0.0).rate() is None
    assert a_calibration(swath_ft=0.0).rate() is None
    assert a_calibration().rate() is not None


def test_the_calibration_falls_due_a_month_later() -> None:
    assert a_calibration().due() == dt.date(2025, 7, 12)


def test_a_negative_droplet_or_swath_is_refused() -> None:
    with pytest.raises(UsageError):
        a_calibration(droplet=-1.0)
    with pytest.raises(UsageError):
        a_calibration(swath_ft=-1.0)
