from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, formulary
from dipcount.errors import LabelViolation, RuleViolation
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH, TECHNICIAN
from dipcount.model.block import PHONE
from dipcount.model.exclusion import APIARY, AQUACULTURE, ORGANIC
from dipcount.service import adulticide
from dipcount.store import Book, applicators, blocks, exclusions, inventory, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 4, 1)
START = clock.moment("2025-07-10 21:10")
END = clock.moment("2025-07-10 22:40")


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    blocks.add(book, "north", "Ardmore east grid", 640.0, LISTED, road_miles=18.4)
    blocks.add(book, "north", "Weir street grid", 320.0, LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Kestrel ULV", "25K-0114", quantity("30 gal"), LISTED)
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    applicators.add(
        book,
        "D. Uzoma",
        "PA-44193",
        TECHNICIAN,
        (CORE, PUBLIC_HEALTH),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
        supervisor="AP-001",
    )
    return book


def clear(book: Book, **rest: object) -> adulticide.Window:
    return adulticide.window(book, "BK-0001", START, wind_mph=4.5, temperature=74.0, **rest)  # type: ignore[arg-type]


def tell(book: Book, entry: str, hours: int = 60) -> None:
    blocks.give(
        book,
        entry,
        "BK-0001",
        START - dt.timedelta(hours=hours),
        clock.moment("2025-07-10 20:00"),
        clock.moment("2025-07-11 02:00"),
        PHONE,
        "T. Okwuosa",
    )


def test_an_empty_block_on_a_good_night_is_clear(district: Book) -> None:
    found = clear(district)
    assert found.allowed
    assert "clear" in found.line()


def test_still_air_is_a_refusal_and_not_a_perfect_night(district: Book) -> None:
    found = adulticide.window(district, "BK-0001", START, wind_mph=0.4, temperature=74.0)
    assert not found.allowed
    assert found.refusals[0].rule == "spray.wind"
    assert "inversion" in found.refusals[0].detail


def test_too_much_wind_is_the_other_end_of_the_same_band(district: Book) -> None:
    found = adulticide.window(district, "BK-0001", START, wind_mph=14.0, temperature=74.0)
    assert not found.allowed
    assert "ceiling" in found.refusals[0].detail


def test_both_ends_of_the_band_are_inside(district: Book) -> None:
    low = adulticide.window(district, "BK-0001", START, wind_mph=1.0, temperature=74.0)
    high = adulticide.window(district, "BK-0001", START, wind_mph=10.0, temperature=74.0)
    assert low.allowed
    assert high.allowed


def test_a_cold_night_is_refused(district: Book) -> None:
    found = adulticide.window(district, "BK-0001", START, wind_mph=4.5, temperature=44.0)
    assert not found.allowed
    assert any(one.rule == "spray.temperature" for one in found.refusals)


def test_no_reading_at_all_is_a_refusal(district: Book) -> None:
    found = adulticide.window(district, "BK-0001", START)
    assert not found.allowed
    assert {one.rule for one in found.refusals} == {"spray.wind", "spray.temperature"}


def test_the_truck_does_not_run_in_the_afternoon(district: Book) -> None:
    found = adulticide.window(
        district, "BK-0001", clock.moment("2025-07-10 15:00"), wind_mph=4.5, temperature=74.0
    )
    assert not found.allowed
    assert any(one.rule == "spray.hours" for one in found.refusals)


def test_the_small_hours_are_inside_the_window(district: Book) -> None:
    found = adulticide.window(
        district, "BK-0001", clock.moment("2025-07-11 01:00"), wind_mph=4.5, temperature=74.0
    )
    assert found.allowed


def test_a_run_over_more_than_the_block_is_refused(district: Book) -> None:
    found = clear(district, acres=900.0)
    assert not found.allowed
    assert any(one.rule == "spray.acres" for one in found.refusals)


def test_part_of_a_block_can_be_run(district: Book) -> None:
    found = clear(district, acres=200.0)
    assert found.allowed
    assert found.acres == 200.0


def test_a_retired_block_is_off_the_run_list(district: Book) -> None:
    blocks.retire(district, "BK-0001", dt.date(2025, 6, 1))
    found = clear(district)
    assert any(one.rule == "spray.block" for one in found.refusals)


def test_an_apiary_inside_the_block_has_to_be_told(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    blocks.link(district, "BK-0001", "EX-0001")
    found = clear(district)
    assert not found.allowed
    assert found.refusals[0].rule == "spray.notice"
    assert found.untold == ("EX-0001",)


def test_telling_them_in_time_clears_the_block(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    blocks.link(district, "BK-0001", "EX-0001")
    tell(district, "EX-0001")
    found = clear(district)
    assert found.allowed
    assert found.told == ("EX-0001",)


def test_telling_them_too_late_does_not(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    blocks.link(district, "BK-0001", "EX-0001")
    tell(district, "EX-0001", hours=12)
    found = clear(district)
    assert not found.allowed
    assert found.untold == ("EX-0001",)


def test_an_organic_farm_wants_less_warning_than_an_apiary(district: Book) -> None:
    exclusions.add(district, ORGANIC, "Halloran organics", "north", LISTED)
    blocks.link(district, "BK-0001", "EX-0001")
    tell(district, "EX-0001", hours=30)
    assert clear(district).allowed


def test_the_same_warning_is_not_enough_for_an_apiary(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")
    blocks.link(district, "BK-0001", "EX-0001")
    tell(district, "EX-0001", hours=30)
    assert not clear(district).allowed


def test_a_hatchery_takes_the_block_off_whatever_anybody_was_told(district: Book) -> None:
    exclusions.add(district, AQUACULTURE, "Prewitt trout", "north", LISTED, contact="J. P")
    blocks.link(district, "BK-0001", "EX-0001")
    tell(district, "EX-0001")
    found = clear(district)
    assert not found.allowed
    assert found.barred == ("EX-0001",)
    assert any(one.rule == "spray.absolute" for one in found.refusals)


def test_an_entry_off_the_register_stops_mattering(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")
    blocks.link(district, "BK-0001", "EX-0001")
    exclusions.remove(district, "EX-0001", dt.date(2025, 6, 1))
    assert clear(district).allowed


def test_who_still_has_to_be_told_is_listed(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")
    exclusions.add(district, ORGANIC, "Halloran organics", "north", LISTED)
    blocks.link(district, "BK-0001", "EX-0001")
    blocks.link(district, "BK-0001", "EX-0002")
    tell(district, "EX-0002", hours=30)
    waiting = adulticide.who_to_tell(district, "BK-0001", START)
    assert [one.id for one in waiting] == ["EX-0001"]


def test_the_notice_deadline_is_the_earliest_anybody_wants(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")
    exclusions.add(district, ORGANIC, "Halloran organics", "north", LISTED)
    blocks.link(district, "BK-0001", "EX-0001")
    blocks.link(district, "BK-0001", "EX-0002")
    by = adulticide.notice_deadline(district, "BK-0001", START)
    assert by is not None
    assert clock.stamp(by) == "2025-07-08 21:10"


def test_a_block_with_nobody_on_the_register_has_no_deadline(district: Book) -> None:
    assert adulticide.notice_deadline(district, "BK-0001", START) is None


def test_a_run_is_recorded_and_drawn_off_the_lot(district: Book) -> None:
    made = adulticide.spray(
        district,
        "AP-001",
        "BK-0001",
        "LT-0001",
        START,
        END,
        quantity("1.4 gal"),
        wind_mph=4.5,
        temperature=74.0,
        wind_from="SW",
    )
    assert made.id == "RN-250710-01"
    assert made.licence == "PA-44192"
    assert inventory.stock(district, "LT-0001").left == quantity("28.6 gal")


def test_a_run_on_a_still_night_is_refused_and_draws_nothing(district: Book) -> None:
    with pytest.raises(RuleViolation, match="inversion"):
        adulticide.spray(
            district,
            "AP-001",
            "BK-0001",
            "LT-0001",
            START,
            END,
            quantity("1.4 gal"),
            wind_mph=0.2,
            temperature=74.0,
        )
    assert inventory.stock(district, "LT-0001").left == quantity("30 gal")
    assert district.count("run") == 0


def test_a_larvicide_does_not_go_through_a_fogger(district: Book) -> None:
    with pytest.raises(LabelViolation, match="fogger"):
        adulticide.spray(
            district,
            "AP-001",
            "BK-0001",
            "LT-0002",
            START,
            END,
            quantity("40 lb"),
            wind_mph=4.5,
            temperature=74.0,
        )


def test_a_technician_cannot_apply_the_restricted_fog(district: Book) -> None:
    with pytest.raises(RuleViolation, match="may not apply"):
        adulticide.spray(
            district,
            "AP-002",
            "BK-0001",
            "LT-0001",
            START,
            END,
            quantity("1.4 gal"),
            wind_mph=4.5,
            temperature=74.0,
        )


def test_an_out_of_date_lot_is_refused(district: Book) -> None:
    inventory.receive(
        district,
        "Kestrel ULV",
        "23K-0001",
        quantity("10 gal"),
        dt.date(2023, 4, 1),
        expires_on=dt.date(2025, 3, 31),
    )
    with pytest.raises(RuleViolation, match="out of date"):
        adulticide.spray(
            district,
            "AP-001",
            "BK-0001",
            "LT-0003",
            START,
            END,
            quantity("1.4 gal"),
            wind_mph=4.5,
            temperature=74.0,
        )


def test_the_board_covers_every_open_block(district: Book) -> None:
    found = adulticide.tonight_board(district, START, wind_mph=4.5, temperature=74.0)
    assert [one.block for one in found] == ["BK-0001", "BK-0002"]
    assert all(one.allowed for one in found)


def test_the_board_holds_the_block_with_somebody_untold(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")
    blocks.link(district, "BK-0001", "EX-0001")
    found = adulticide.tonight_board(district, START, wind_mph=4.5, temperature=74.0)
    held = [one for one in found if not one.allowed]
    assert [one.block for one in held] == ["BK-0001"]
    assert "held" in held[0].line()


def test_the_register_inside_a_block_is_listed(district: Book) -> None:
    exclusions.add(district, APIARY, "Ferrand apiary", "north", LISTED, contact="M. F")
    blocks.link(district, "BK-0001", "EX-0001")
    found = adulticide.register_in(district, "BK-0001", dt.date(2025, 7, 10))
    assert [one.id for one in found] == ["EX-0001"]


def test_the_window_carries_the_readings_it_was_given(district: Book) -> None:
    found = clear(district)
    assert found.wind_mph == Decimal("4.5")
    assert found.temperature == Decimal("74.0")
