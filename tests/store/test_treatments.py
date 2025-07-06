from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock, formulary
from dipcount.errors import NotFound
from dipcount.store import Book, inventory, sites, treatments, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    sites.add(book, "north", "Pettit pond", "retention_pond", quantity("3 acre"), LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    inventory.receive(book, "Sphaerix WG", "24S-0042", quantity("200 lb"), LISTED)
    return book


def apply(
    book: Book,
    site: str = "SI-0001",
    lot: str = "LT-0001",
    day: str = "2025-06-04",
    amount: str = "36 lb",
    extent: str = "6 acre",
) -> str:
    made = treatments.write(
        book,
        site,
        lot,
        clock.moment(f"{day} 10:40"),
        "K. Brennaman",
        quantity(extent),
        quantity(amount),
    )
    return made.id


def test_a_treatment_is_numbered_by_its_day(district: Book) -> None:
    assert apply(district) == "TX-250604-01"
    assert apply(district, site="SI-0002", extent="3 acre", amount="18 lb") == "TX-250604-02"


def test_the_product_comes_off_the_lot(district: Book) -> None:
    made = treatments.get(district, apply(district))
    assert made.product == "PD-0001"


def test_a_treatment_at_a_site_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        apply(district, site="SI-0099")


def test_a_treatment_out_of_a_lot_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        apply(district, lot="LT-0099")


def test_treatments_narrow_by_site_and_product(district: Book) -> None:
    apply(district)
    apply(district, site="SI-0002", extent="3 acre", amount="18 lb")
    apply(district, lot="LT-0002", amount="30 lb")
    window = (dt.date(2025, 6, 1), dt.date(2025, 6, 30))
    assert len(treatments.between(district, *window)) == 3
    assert len(treatments.between(district, *window, site_id="SI-0001")) == 2
    assert len(treatments.between(district, *window, product_id="PD-0005")) == 1


def test_a_day_and_a_week_gather_what_was_made(district: Book) -> None:
    apply(district, day="2025-06-04")
    apply(district, day="2025-06-05")
    apply(district, day="2025-06-20")
    assert len(treatments.on_day(district, dt.date(2025, 6, 4))) == 1
    assert len(treatments.in_week(district, 2025, 23)) == 2


def test_the_treatments_at_a_site_come_back_oldest_first(district: Book) -> None:
    apply(district, day="2025-06-20")
    apply(district, day="2025-06-04")
    found = treatments.for_site(district, "SI-0001")
    assert [one.on.day for one in found] == [4, 20]


def test_the_treatments_out_of_a_lot_are_listed(district: Book) -> None:
    apply(district)
    apply(district, lot="LT-0002", amount="30 lb")
    assert len(treatments.for_lot(district, "LT-0002")) == 1


def test_the_last_treatment_can_be_asked_for_as_of_a_day(district: Book) -> None:
    apply(district, day="2025-06-04")
    apply(district, day="2025-06-20")
    last = treatments.last_at(district, "SI-0001")
    assert last is not None
    assert last.on.day == 20
    earlier = treatments.last_at(district, "SI-0001", on=dt.date(2025, 6, 10))
    assert earlier is not None
    assert earlier.on.day == 4


def test_the_last_treatment_can_be_narrowed_to_a_product(district: Book) -> None:
    apply(district, day="2025-06-04")
    apply(district, day="2025-06-20", lot="LT-0002", amount="30 lb")
    found = treatments.last_at(district, "SI-0001", product_id="PD-0001")
    assert found is not None
    assert found.on.day == 4


def test_a_site_never_treated_has_no_last_treatment(district: Book) -> None:
    assert treatments.last_at(district, "SI-0002") is None


def test_the_season_total_adds_a_product_up_at_a_site(district: Book) -> None:
    apply(district, day="2025-06-04", amount="36 lb")
    apply(district, day="2025-06-20", amount="24 lb")
    apply(district, day="2025-06-20", lot="LT-0002", amount="30 lb")
    assert treatments.season_total(district, "SI-0001", "PD-0001", 2025) == quantity("60 lb")


def test_the_season_total_stops_at_the_year_end(district: Book) -> None:
    apply(district, day="2025-06-04", amount="36 lb")
    apply(district, day="2026-06-04", amount="24 lb")
    assert treatments.season_total(district, "SI-0001", "PD-0001", 2025) == quantity("36 lb")
    assert treatments.season_total(district, "SI-0001", "PD-0001", 2026) == quantity("24 lb")


def test_a_season_with_nothing_in_it_comes_back_in_the_unit_asked_for(district: Book) -> None:
    found = treatments.season_total(district, "SI-0002", "PD-0001", 2025, unit="lb")
    assert found == quantity("0 lb")


def test_the_season_total_converts_if_asked(district: Book) -> None:
    apply(district, day="2025-06-04", amount="36 lb")
    found = treatments.season_total(district, "SI-0001", "PD-0001", 2025, unit="oz")
    assert found == quantity("576 oz")


def test_the_applicators_are_listed(district: Book) -> None:
    apply(district)
    assert treatments.applicators(district) == ["K. Brennaman"]


def test_a_missing_treatment(district: Book) -> None:
    with pytest.raises(NotFound):
        treatments.get(district, "TX-250604-09")
