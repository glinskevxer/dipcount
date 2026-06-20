from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, formulary
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.report import use_report as report
from dipcount.service import adulticide, larvicide
from dipcount.store import (
    Book,
    applicators,
    blocks,
    inventory,
    products,
    sites,
    treatments,
    upgrade,
    zones,
)
from dipcount.units import quantity, rate

LISTED = dt.date(2025, 3, 1)
SEASON = (dt.date(2025, 1, 1), dt.date(2025, 12, 31))


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    blocks.add(book, "north", "Ardmore east grid", 640.0, LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    inventory.receive(book, "Kestrel ULV", "25K-0114", quantity("30 gal"), LISTED)
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    return book


def treat(book: Book, day: str = "2025-06-04") -> None:
    larvicide.treat(book, "AP-001", "SI-0001", "LT-0001", clock.moment(f"{day} 10:40"))


def fog(book: Book, day: str = "2025-07-10") -> None:
    adulticide.spray(
        book,
        "AP-001",
        "BK-0001",
        "LT-0002",
        clock.moment(f"{day} 21:10"),
        clock.moment(f"{day} 22:40"),
        quantity("1.4 gal"),
        wind_mph=4.5,
        temperature=74.0,
    )


def test_an_empty_season_files_nothing(district: Book) -> None:
    found = report.season(district, 2025)
    assert found.filed == []
    assert found.held == []
    assert "0 rows" in found.sheet().render()


def test_both_kinds_of_application_land_on_one_return(district: Book) -> None:
    treat(district)
    fog(district)
    found = report.season(district, 2025)
    assert len(found.filed) == 2
    assert {one.kind for one in found.filed} == {"cattail marsh", "spray block"}


def test_the_rows_come_out_in_day_order(district: Book) -> None:
    fog(district, day="2025-07-10")
    treat(district, day="2025-06-04")
    found = report.season(district, 2025)
    assert [one.on.month for one in found.filed] == [6, 7]


def test_every_row_carries_the_registration_and_the_licence(district: Book) -> None:
    treat(district)
    line = report.season(district, 2025).filed[0]
    assert line.product.registration == "73049-20"
    assert line.licence == "PA-44192"
    assert "73049-20" in "".join(line.cells())


def test_the_rate_is_worked_out_for_the_row(district: Book) -> None:
    treat(district)
    line = report.season(district, 2025).filed[0]
    assert line.rate.endswith("/acre")


def test_a_row_with_no_licence_is_held_back(district: Book) -> None:
    treat(district)
    district.run("UPDATE treatment SET licence = ''")
    found = report.season(district, 2025)
    assert found.filed == []
    assert len(found.held) == 1
    assert "held back" in found.render()


def test_a_held_row_does_not_reach_the_totals(district: Book) -> None:
    treat(district)
    district.run("UPDATE treatment SET licence = ''")
    assert report.season(district, 2025).by_product() == {}


def test_the_products_are_totalled(district: Book) -> None:
    treat(district, day="2025-06-04")
    treat(district, day="2025-06-14")
    found = report.season(district, 2025)
    assert found.by_product()["Bactilore G"] == quantity("75 lb")


def test_the_actives_are_totalled_off_the_share(district: Book) -> None:
    treat(district)
    found = report.season(district, 2025)
    active = "Bacillus thuringiensis subspecies israelensis"
    assert found.by_active()[active] == quantity("1.6875 lb")


def test_a_pouch_reaches_the_total_once_the_shelf_knows_what_one_weighs(
    district: Book,
) -> None:
    inventory.receive(district, "Bactilore WSP", "24W-0801", quantity("500 each"), LISTED)
    sites.add(district, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    treat(district)
    larvicide.treat(
        district,
        "AP-001",
        "SI-0002",
        "LT-0003",
        clock.moment("2025-06-05 10:40"),
    )
    found = report.season(district, 2025)
    active = "Bacillus thuringiensis subspecies israelensis"
    assert found.by_active()[active] > quantity("1.6875 lb")
    assert found.counted_actives() == {}


def test_a_product_with_no_unit_weight_is_shown_rather_than_lost(district: Book) -> None:
    products.add(
        district,
        "Ridgeline briquets",
        "99999-4",
        "Ridgeline",
        "S-methoprene",
        Decimal("2.1"),
        "briquet",
        "larvicide",
        LISTED,
    )
    products.label(
        district,
        "PD-0011",
        "catch_basin",
        rate("1 briquet/basin"),
        rate("1 briquet/basin"),
    )
    inventory.receive(district, "Ridgeline briquets", "R-0001", quantity("200 each"), LISTED)
    sites.add(district, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    larvicide.treat(
        district,
        "AP-001",
        "SI-0002",
        "LT-0003",
        clock.moment("2025-06-05 10:40"),
    )
    found = report.season(district, 2025)
    assert found.counted_actives()["S-methoprene"].unit == "each"
    assert "not weighable" in found.totals_sheet().render()


def test_the_restricted_applications_are_kept_apart(district: Book) -> None:
    treat(district)
    fog(district)
    found = report.season(district, 2025)
    assert [one.record for one in found.restricted()] == ["RN-250710-01"]


def test_the_totals_sheet_names_both_kinds_of_total(district: Book) -> None:
    treat(district)
    text = report.season(district, 2025).totals_sheet().render()
    assert "product" in text
    assert "active" in text


def test_the_return_comes_out_as_a_file(district: Book) -> None:
    treat(district)
    text = report.season(district, 2025).csv()
    assert text.splitlines()[0].startswith("day,record,place")
    assert "73049-20" in text


def test_a_window_smaller_than_the_season(district: Book) -> None:
    treat(district, day="2025-06-04")
    treat(district, day="2025-07-14")
    found = report.use_return(district, dt.date(2025, 6, 1), dt.date(2025, 6, 30))
    assert len(found.filed) == 1


def test_the_columns_are_the_ones_declared(district: Book) -> None:
    treat(district)
    line = report.season(district, 2025).filed[0]
    assert len(line.cells()) == len(report.COLUMNS)


def test_records_are_kept_two_years_past_the_season() -> None:
    assert report.keep_until(2025) == dt.date(2027, 12, 31)
    assert not report.destroyable(2025, dt.date(2027, 12, 31))
    assert report.destroyable(2025, dt.date(2028, 1, 1))


def test_a_treatment_over_nothing_never_reaches_the_return(district: Book) -> None:
    treat(district)
    assert treatments.between(district, *SEASON)[0].extent.amount > 0
    assert report.season(district, 2025).filed[0].area.amount > 0
