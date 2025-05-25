from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount.errors import NotFound, UsageError
from dipcount.model.product import (
    ADULTICIDE,
    DANGER,
    LARVICIDE,
    Label,
    Product,
)
from dipcount.units import quantity, rate

ADDED = dt.date(2025, 1, 15)


def a_label(**changes: object) -> Label:
    fields: dict[str, object] = {
        "habitat": "cattail_marsh",
        "low": rate("2.5 lb/acre"),
        "high": rate("10 lb/acre"),
    }
    fields.update(changes)
    return Label(**fields)  # type: ignore[arg-type]


def a_product(**changes: object) -> Product:
    fields: dict[str, object] = {
        "id": "PD-0001",
        "name": "Bactilore G",
        "registration": "73049-20",
        "maker": "Vestrum Biologicals",
        "active": "Bacillus thuringiensis subspecies israelensis",
        "percent": Decimal("4.5"),
        "form": "granule",
        "purpose": LARVICIDE,
        "added_on": ADDED,
    }
    fields.update(changes)
    return Product(**fields)  # type: ignore[arg-type]


def test_a_label_is_a_range_and_not_a_figure() -> None:
    label = a_label()
    assert label.covers(rate("2.5 lb/acre"))
    assert label.covers(rate("6 lb/acre"))
    assert label.covers(rate("10 lb/acre"))
    assert not label.covers(rate("2 lb/acre"))
    assert not label.covers(rate("10.5 lb/acre"))


def test_a_rate_in_another_unit_still_compares() -> None:
    assert a_label().covers(rate("96 oz/acre"))
    assert not a_label().covers(rate("16 oz/acre"))


def test_a_rate_written_against_the_wrong_thing_is_not_covered() -> None:
    assert not a_label().covers(rate("6 lb/each"))


def test_the_middle_of_the_range_is_where_a_plan_starts() -> None:
    assert a_label().middle().amount == quantity("6.25 lb")


def test_a_rate_range_has_to_run_upwards() -> None:
    with pytest.raises(UsageError, match="below the bottom"):
        a_label(low=rate("10 lb/acre"), high=rate("2.5 lb/acre"))


def test_both_ends_use_one_unit() -> None:
    with pytest.raises(UsageError):
        a_label(low=rate("40 oz/acre"), high=rate("10 lb/acre"))


def test_a_rate_has_to_suit_the_habitat_it_is_written_for() -> None:
    with pytest.raises(UsageError, match="measured in each"):
        a_label(habitat="catch_basin")
    assert (
        a_label(
            habitat="catch_basin",
            low=rate("1 briquet/basin"),
            high=rate("2 briquet/basin"),
        ).per
        == "each"
    )


def test_a_label_for_a_habitat_that_does_not_exist() -> None:
    with pytest.raises(NotFound):
        a_label(habitat="swimming_pool")


def test_a_negative_interval_is_refused() -> None:
    with pytest.raises(UsageError):
        a_label(interval_days=-1)


def test_a_label_line_reads_like_a_label() -> None:
    line = a_label(season_max=quantity("30 lb"), interval_days=21).line()
    assert "2.5 lb to 10 lb per acre" in line
    assert "no more than 30 lb a season" in line
    assert "21 days apart" in line


def test_a_product_needs_a_name_and_a_registration() -> None:
    with pytest.raises(UsageError):
        a_product(name=" ")
    with pytest.raises(UsageError):
        a_product(registration="")


def test_an_unknown_purpose_or_signal_word_is_refused() -> None:
    with pytest.raises(UsageError):
        a_product(purpose="repellent")
    with pytest.raises(UsageError):
        a_product(signal="shouty")


def test_a_formulation_the_district_does_not_handle() -> None:
    with pytest.raises(UsageError):
        a_product(form="fog")


def test_the_share_of_active_ingredient_is_a_share() -> None:
    with pytest.raises(UsageError):
        a_product(percent=Decimal(0))
    with pytest.raises(UsageError):
        a_product(percent=Decimal(101))
    assert a_product(percent=Decimal(100)).percent == 100


def test_a_product_cannot_be_withdrawn_before_it_was_added() -> None:
    with pytest.raises(UsageError):
        a_product(withdrawn_on=ADDED - dt.timedelta(days=1))


def test_a_product_is_on_the_shelf_between_its_dates() -> None:
    product = a_product(withdrawn_on=dt.date(2025, 12, 31))
    assert not product.on_shelf(dt.date(2025, 1, 1))
    assert product.on_shelf(dt.date(2025, 6, 1))
    assert not product.on_shelf(dt.date(2026, 1, 1))


def test_a_label_cannot_carry_two_entries_for_one_habitat() -> None:
    with pytest.raises(UsageError, match="two entries"):
        a_product(labels=(a_label(), a_label()))


def test_the_labelled_habitats_are_the_ones_with_a_rate() -> None:
    product = a_product(
        labels=(
            a_label(),
            a_label(habitat="retention_pond", low=rate("2.5 lb/acre"), high=rate("8 lb/acre")),
        ),
    )
    assert product.labelled_habitats() == ["cattail_marsh", "retention_pond"]
    assert product.label_for("cattail_marsh") is not None
    assert product.label_for("lagoon") is None


def test_the_active_ingredient_comes_off_the_share() -> None:
    product = a_product(percent=Decimal("4.5"))
    assert product.active_in(quantity("100 lb")) == quantity("4.5 lb")


def test_two_products_at_the_same_rate_carry_different_active() -> None:
    weak = a_product(percent=Decimal("4.5"))
    strong = a_product(percent=Decimal("37"))
    assert strong.active_in(quantity("10 lb")) > weak.active_in(quantity("10 lb"))


def test_a_restricted_adulticide_carries_its_signal_word() -> None:
    product = a_product(
        purpose=ADULTICIDE,
        form="liquid",
        restricted=True,
        signal=DANGER,
        reentry=12,
    )
    assert product.restricted
    assert product.signal == DANGER
    assert product.reentry == 12
