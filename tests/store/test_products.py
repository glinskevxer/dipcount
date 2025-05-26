from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.product import ADULTICIDE, LARVICIDE
from dipcount.store import Book, upgrade
from dipcount.store import products as store
from dipcount.units import quantity, rate

ADDED = dt.date(2025, 1, 15)


def shelf(book: Book) -> None:
    store.add(
        book,
        "Bactilore G",
        "73049-20",
        "Vestrum Biologicals",
        "Bacillus thuringiensis subspecies israelensis",
        Decimal("4.5"),
        "granule",
        LARVICIDE,
        ADDED,
    )
    store.add(
        book,
        "Hesper 30 briquets",
        "8329-114",
        "Hesper Chemical",
        "S-methoprene",
        Decimal("1.8"),
        "briquet",
        LARVICIDE,
        ADDED,
    )


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    shelf(book)
    return book


def test_a_product_is_numbered_and_found_three_ways(district: Book) -> None:
    assert store.get(district, "PD-0001").name == "Bactilore G"
    assert store.resolve(district, "Bactilore G").id == "PD-0001"
    assert store.resolve(district, "8329-114").id == "PD-0002"
    with pytest.raises(NotFound):
        store.resolve(district, "Nothing")


def test_a_name_and_a_registration_are_each_used_once(district: Book) -> None:
    with pytest.raises(Duplicate):
        store.add(
            district,
            "Bactilore G",
            "99999-1",
            "Other",
            "Bti",
            Decimal(4),
            "granule",
            LARVICIDE,
            ADDED,
        )
    with pytest.raises(Duplicate):
        store.add(
            district,
            "Something else",
            "73049-20",
            "Other",
            "Bti",
            Decimal(4),
            "granule",
            LARVICIDE,
            ADDED,
        )


def test_products_narrow_by_purpose_form_and_active(district: Book) -> None:
    store.add(
        district,
        "Kestrel ULV",
        "1021-1873",
        "Kestrel",
        "permethrin",
        Decimal("4.6"),
        "liquid",
        ADULTICIDE,
        ADDED,
        restricted=True,
        signal="warning",
    )
    assert len(store.all_products(district)) == 3
    assert len(store.all_products(district, purpose=ADULTICIDE)) == 1
    assert len(store.all_products(district, form="granule")) == 1
    assert len(store.all_products(district, active="S-methoprene")) == 1


def test_a_withdrawn_product_leaves_the_shelf(district: Book) -> None:
    store.withdraw(district, "PD-0001", dt.date(2025, 9, 1), "registration lapsed")
    assert len(store.on_shelf(district, dt.date(2025, 8, 1))) == 2
    assert len(store.on_shelf(district, dt.date(2025, 9, 2))) == 1
    assert "lapsed" in store.get(district, "PD-0001").note


def test_a_product_is_not_withdrawn_twice(district: Book) -> None:
    store.withdraw(district, "PD-0001", dt.date(2025, 9, 1))
    with pytest.raises(RuleViolation):
        store.withdraw(district, "PD-0001", dt.date(2025, 10, 1))


def test_a_product_cannot_be_withdrawn_before_it_was_added(district: Book) -> None:
    with pytest.raises(RuleViolation):
        store.withdraw(district, "PD-0001", dt.date(2024, 1, 1))


def test_a_label_is_written_against_a_habitat(district: Book) -> None:
    after = store.label(
        district,
        "PD-0001",
        "cattail_marsh",
        rate("2.5 lb/acre"),
        rate("10 lb/acre"),
        season_max=quantity("30 lb"),
        interval_days=21,
    )
    entry = after.label_for("cattail_marsh")
    assert entry is not None
    assert entry.covers(rate("6 lb/acre"))
    assert entry.interval_days == 21
    assert entry.season_max == quantity("30 lb")


def test_a_habitat_that_does_not_take_the_formulation_is_refused(district: Book) -> None:
    with pytest.raises(RuleViolation, match="does not take"):
        store.label(
            district,
            "PD-0001",
            "container",
            rate("1 lb/each"),
            rate("2 lb/each"),
        )


def test_a_briquet_belongs_in_a_basin(district: Book) -> None:
    after = store.label(
        district,
        "PD-0002",
        "catch_basin",
        rate("1 briquet/basin"),
        rate("1 briquet/basin"),
        interval_days=150,
    )
    assert after.labelled_habitats() == ["catch_basin"]


def test_one_habitat_takes_one_label_entry(district: Book) -> None:
    store.label(district, "PD-0001", "cattail_marsh", rate("2.5 lb/acre"), rate("10 lb/acre"))
    with pytest.raises(Duplicate):
        store.label(district, "PD-0001", "cattail_marsh", rate("3 lb/acre"), rate("9 lb/acre"))


def test_labels_come_back_with_the_product(district: Book) -> None:
    store.label(district, "PD-0001", "cattail_marsh", rate("2.5 lb/acre"), rate("10 lb/acre"))
    store.label(district, "PD-0001", "retention_pond", rate("2.5 lb/acre"), rate("8 lb/acre"))
    found = store.get(district, "PD-0001")
    assert found.labelled_habitats() == ["cattail_marsh", "retention_pond"]


def test_the_products_for_a_habitat_are_the_ones_labelled_for_it(district: Book) -> None:
    store.label(district, "PD-0001", "cattail_marsh", rate("2.5 lb/acre"), rate("10 lb/acre"))
    store.label(
        district, "PD-0002", "catch_basin", rate("1 briquet/basin"), rate("1 briquet/basin")
    )
    assert [one.id for one in store.for_habitat(district, "cattail_marsh")] == ["PD-0001"]
    assert [one.id for one in store.for_habitat(district, "catch_basin")] == ["PD-0002"]
    assert store.for_habitat(district, "lagoon") == []


def test_a_withdrawn_product_drops_out_of_the_habitat_list(district: Book) -> None:
    store.label(district, "PD-0001", "cattail_marsh", rate("2.5 lb/acre"), rate("10 lb/acre"))
    store.withdraw(district, "PD-0001", dt.date(2025, 6, 1))
    assert store.for_habitat(district, "cattail_marsh", on=dt.date(2025, 7, 1)) == []
    assert len(store.for_habitat(district, "cattail_marsh", on=dt.date(2025, 5, 1))) == 1


def test_the_actives_on_the_shelf_are_listed(district: Book) -> None:
    assert store.actives(district) == [
        "Bacillus thuringiensis subspecies israelensis",
        "S-methoprene",
    ]


def test_a_missing_product(district: Book) -> None:
    with pytest.raises(NotFound):
        store.get(district, "PD-0099")
