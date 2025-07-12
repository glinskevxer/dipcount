from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock, formulary
from dipcount.errors import LabelViolation, RuleViolation
from dipcount.service import larvicide
from dipcount.store import Book, inventory, products, sites, treatments, upgrade, zones
from dipcount.units import quantity, rate

LISTED = dt.date(2025, 3, 1)
ON = dt.date(2025, 6, 4)
AT = clock.moment("2025-06-04 10:40")


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    inventory.receive(book, "Bactilore WSP", "24W-0801", quantity("500 each"), LISTED)
    return book


def test_a_plan_takes_the_middle_of_the_range(district: Book) -> None:
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON)
    assert made.allowed
    assert made.rate == rate("6.25 lb/acre")
    assert made.amount == quantity("37.5 lb")


def test_the_strength_moves_the_rate_inside_the_range(district: Book) -> None:
    low = larvicide.plan(district, "SI-0001", "Bactilore G", ON, strength=larvicide.LOW)
    high = larvicide.plan(district, "SI-0001", "Bactilore G", ON, strength=larvicide.HIGH)
    assert low.rate == rate("2.5 lb/acre")
    assert high.rate == rate("10 lb/acre")


def test_a_rate_outside_the_range_is_a_label_violation(district: Book) -> None:
    over = larvicide.plan(district, "SI-0001", "Bactilore G", ON, rate=rate("12 lb/acre"))
    assert not over.allowed
    assert over.refusals[0].rule == "label.rate"
    with pytest.raises(LabelViolation):
        over.check()


def test_a_product_not_labelled_for_the_habitat_is_refused(district: Book) -> None:
    made = larvicide.plan(district, "SI-0001", "Hesper 30 briquets", ON)
    assert not made.allowed
    assert made.refusals[0].rule in {"label.form", "label.site"}


def test_a_pouch_goes_into_a_basin_and_a_granule_does_not(district: Book) -> None:
    pouches = larvicide.plan(district, "SI-0002", "Bactilore WSP", ON)
    granules = larvicide.plan(district, "SI-0002", "Bactilore G", ON)
    assert pouches.allowed
    assert not granules.allowed


def test_a_treatment_over_more_ground_than_the_site_has(district: Book) -> None:
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON, extent=quantity("9 acre"))
    assert not made.allowed
    assert any(one.rule == "treat.extent" for one in made.refusals)


def test_an_extent_in_the_wrong_unit_is_refused(district: Book) -> None:
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON, extent=quantity("6 each"))
    assert not made.allowed
    assert made.refusals[0].rule == "treat.extent"


def test_part_of_a_site_can_be_treated(district: Book) -> None:
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON, extent=quantity("2 acre"))
    assert made.allowed
    assert made.amount == quantity("12.5 lb")


def test_a_withdrawn_product_cannot_be_applied(district: Book) -> None:
    products.withdraw(district, "PD-0001", dt.date(2025, 5, 1))
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON)
    assert not made.allowed
    assert any(one.rule == "label.shelf" for one in made.refusals)


def test_a_retired_site_cannot_be_treated(district: Book) -> None:
    sites.retire(district, "SI-0001", dt.date(2025, 5, 1))
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON)
    assert not made.allowed
    assert any(one.rule == "site.retired" for one in made.refusals)


def test_a_treatment_draws_the_product_off_the_lot(district: Book) -> None:
    made = larvicide.treat(district, "K. Brennaman", "SI-0001", "LT-0001", AT)
    assert made.amount == quantity("37.5 lb")
    assert inventory.stock(district, "LT-0001").left == quantity("362.5 lb")
    assert [one.reference for one in inventory.for_reference(district, made.id)] == [made.id]


def test_a_treatment_leaves_a_line_on_the_trail(district: Book) -> None:
    made = larvicide.treat(district, "K. Brennaman", "SI-0001", "LT-0001", AT)
    from dipcount.store import audit

    lines = [one for one in audit.about(district, "SI-0001") if one.action == "treated"]
    assert len(lines) == 1
    assert made.id in lines[0].detail


def test_a_work_card_naming_the_wrong_product_for_the_lot(district: Book) -> None:
    with pytest.raises(RuleViolation, match="not a lot"):
        larvicide.treat(
            district,
            "K. B",
            "SI-0001",
            "LT-0001",
            AT,
            product_id="Bactilore WSP",
        )


def test_a_work_card_naming_the_right_product_goes_through(district: Book) -> None:
    made = larvicide.treat(district, "K. B", "SI-0001", "LT-0001", AT, product_id="Bactilore G")
    assert made.product == "PD-0001"


def test_an_out_of_date_lot_is_refused(district: Book) -> None:
    inventory.receive(
        district,
        "Bactilore G",
        "23G-0004",
        quantity("100 lb"),
        dt.date(2023, 3, 1),
        expires_on=dt.date(2025, 3, 31),
    )
    with pytest.raises(RuleViolation, match="out of date"):
        larvicide.treat(district, "K. B", "SI-0001", "LT-0003", AT)


def test_a_lot_with_too_little_left_is_refused(district: Book) -> None:
    inventory.draw(district, "LT-0001", quantity("380 lb"), AT, "K. B")
    with pytest.raises(RuleViolation, match="left"):
        larvicide.treat(district, "K. B", "SI-0001", "LT-0001", AT)


def test_a_refused_treatment_draws_nothing(district: Book) -> None:
    before = inventory.stock(district, "LT-0001").left
    with pytest.raises(LabelViolation):
        larvicide.treat(district, "K. B", "SI-0001", "LT-0001", AT, rate=rate("40 lb/acre"))
    assert inventory.stock(district, "LT-0001").left == before
    assert district.count("treatment") == 0


def test_the_label_interval_holds_a_second_treatment_back(district: Book) -> None:
    larvicide.treat(district, "K. B", "SI-0001", "LT-0001", AT)
    soon = larvicide.plan(district, "SI-0001", "Bactilore G", dt.date(2025, 6, 8))
    later = larvicide.plan(district, "SI-0001", "Bactilore G", dt.date(2025, 6, 12))
    assert any(one.rule == "label.interval" for one in soon.refusals)
    assert later.allowed


def test_the_season_cap_counts_what_has_already_gone_on(district: Book) -> None:
    made = larvicide.plan(district, "SI-0001", "Bactilore G", ON)
    assert made.season_used == quantity("0 lb")
    larvicide.treat(district, "K. B", "SI-0001", "LT-0001", AT)
    after = larvicide.plan(district, "SI-0001", "Bactilore G", dt.date(2025, 6, 12))
    assert after.season_used == quantity("37.5 lb")


def test_the_cap_is_per_acre_and_not_per_site(district: Book) -> None:
    # forty pounds an acre over six acres is two hundred and forty pounds
    for day in range(4, 60, 8):
        when = dt.date(2025, 6, 1) + dt.timedelta(days=day)
        made = larvicide.plan(district, "SI-0001", "Bactilore G", when, strength=larvicide.HIGH)
        if not made.allowed:
            break
        larvicide.treat(
            district,
            "K. B",
            "SI-0001",
            "LT-0001",
            clock.moment(f"{when.isoformat()} 10:40"),
            strength=larvicide.HIGH,
        )
    total = treatments.season_total(district, "SI-0001", "PD-0001", 2025, unit="lb")
    assert total <= quantity("240 lb")


def put_on(district: Book, day: int, at_rate: str) -> None:
    when = dt.date(2025, 6, 1) + dt.timedelta(days=day)
    larvicide.treat(
        district,
        "K. B",
        "SI-0001",
        "LT-0001",
        clock.moment(f"{when.isoformat()} 10:40"),
        rate=rate(at_rate),
    )


def test_a_cap_that_leaves_less_than_the_minimum_leaves_no_treatment(district: Book) -> None:
    # thirty eight and a half of the forty pounds an acre, so one and a half
    # is left and the label will not go below two and a half
    for day in (4, 12, 20):
        put_on(district, day, "10 lb/acre")
    put_on(district, 28, "8.5 lb/acre")
    made = larvicide.plan(district, "SI-0001", "Bactilore G", dt.date(2025, 8, 1))
    assert not made.allowed
    assert made.refusals[0].rule == "label.season"
    assert "under the labelled minimum" in made.refusals[0].detail


def test_a_cap_used_right_up_says_so(district: Book) -> None:
    for day in (4, 12, 20, 28):
        put_on(district, day, "10 lb/acre")
    made = larvicide.plan(district, "SI-0001", "Bactilore G", dt.date(2025, 8, 1))
    assert not made.allowed
    assert "used up" in made.refusals[0].detail


def test_a_cap_with_room_for_a_smaller_treatment_brings_the_rate_down(district: Book) -> None:
    # thirty five of the forty pounds an acre, so five are left and the
    # middle of the range would have been six and a quarter
    for day in (4, 12, 20):
        put_on(district, day, "10 lb/acre")
    put_on(district, 28, "5 lb/acre")
    made = larvicide.plan(district, "SI-0001", "Bactilore G", dt.date(2025, 8, 1))
    assert made.allowed
    assert made.rate is not None
    assert made.rate.amount < quantity("6.25 lb")
    assert made.rate.amount >= quantity("2.5 lb")


def test_the_choices_for_a_site_are_ranked_with_the_allowed_ones_first(district: Book) -> None:
    found = larvicide.choices(district, "SI-0002", ON)
    assert found
    assert found[0].allowed
    assert all(one.site == "SI-0002" for one in found)


def test_a_site_with_nothing_labelled_for_it_has_no_choices(district: Book) -> None:
    sites.add(district, "north", "Barrel", "container", quantity("4 each"), LISTED)
    products.withdraw(district, "PD-0002", dt.date(2025, 5, 1))
    found = larvicide.choices(district, "SI-0003", ON)
    assert all(not one.allowed for one in found)


def test_the_active_applied_at_a_site_adds_up_by_ingredient(district: Book) -> None:
    larvicide.treat(district, "K. B", "SI-0001", "LT-0001", AT)
    found = larvicide.active_applied(district, "SI-0001", 2025)
    assert "Bacillus thuringiensis subspecies israelensis" in found
    assert found["Bacillus thuringiensis subspecies israelensis"] == quantity("1.6875 lb")


def test_a_plan_line_says_what_stopped_it(district: Book) -> None:
    made = larvicide.plan(district, "SI-0002", "Bactilore G", ON)
    assert "refused" in made.line()
    good = larvicide.plan(district, "SI-0001", "Bactilore G", ON)
    assert "37.5 lb" in good.line()
