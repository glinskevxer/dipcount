from __future__ import annotations

import datetime as dt

import pytest

from dipcount import formulary
from dipcount import habitat as hb
from dipcount.errors import NotFound
from dipcount.model.product import ADULTICIDE, LARVICIDE, PURPOSES, SIGNALS
from dipcount.store import Book, products, upgrade
from dipcount.units import quantity

ON = dt.date(2025, 1, 15)


@pytest.fixture
def stocked(book: Book) -> Book:
    upgrade(book)
    formulary.stock(book, ON)
    return book


def test_every_entry_has_a_registration_of_its_own() -> None:
    numbers = [one.registration for one in formulary.SHELF]
    assert len(set(numbers)) == len(numbers)


def test_every_entry_has_a_name_of_its_own() -> None:
    names = [one.name for one in formulary.SHELF]
    assert len(set(names)) == len(names)


def test_every_entry_names_a_real_purpose_signal_and_form() -> None:
    for one in formulary.SHELF:
        assert one.purpose in PURPOSES
        assert one.signal in SIGNALS
        assert one.form in hb.forms()


def test_every_labelled_habitat_takes_the_formulation() -> None:
    for one in formulary.SHELF:
        for habitat, *_ in one.rates:
            assert hb.habitat(habitat).allows(one.form)


def test_the_larvicides_all_carry_a_label_and_the_adulticides_do_not() -> None:
    for one in formulary.SHELF:
        if one.purpose == ADULTICIDE:
            assert one.rates == ()
        else:
            assert one.rates


def test_the_rate_range_runs_upwards_everywhere() -> None:
    for one in formulary.SHELF:
        for _, low, high, *_ in one.rates:
            assert quantity(low) <= quantity(high)


def test_the_season_cap_is_never_below_one_application() -> None:
    for one in formulary.SHELF:
        for _, _, high, cap, _ in one.rates:
            if cap is not None:
                assert quantity(cap) >= quantity(high)


def test_stocking_puts_the_shelf_in_the_book(stocked: Book) -> None:
    assert len(products.all_products(stocked)) == len(formulary.SHELF)
    assert products.find_by_name(stocked, "Bactilore G") is not None


def test_stocking_twice_adds_nothing_the_second_time(stocked: Book) -> None:
    again = formulary.stock(stocked, ON)
    assert again == []
    assert len(products.all_products(stocked)) == len(formulary.SHELF)


def test_only_the_named_entries_can_be_stocked(book: Book) -> None:
    upgrade(book)
    added = formulary.stock(book, ON, only=("Bactilore G",))
    assert len(added) == 1
    assert len(products.all_products(book)) == 1


def test_the_labels_come_across_with_the_products(stocked: Book) -> None:
    found = products.find_by_name(stocked, "Bactilore G")
    assert found is not None
    assert "cattail_marsh" in found.labelled_habitats()
    entry = found.label_for("lagoon")
    assert entry is not None
    assert entry.season_max == quantity("80 lb")


def test_the_pouches_go_into_the_structures(stocked: Book) -> None:
    found = products.find_by_name(stocked, "Bactilore WSP")
    assert found is not None
    for habitat in found.labelled_habitats():
        assert hb.habitat(habitat).counted_one_at_a_time


def test_the_granules_go_over_ground(stocked: Book) -> None:
    found = products.find_by_name(stocked, "Bactilore G")
    assert found is not None
    for habitat in found.labelled_habitats():
        assert not hb.habitat(habitat).counted_one_at_a_time


def test_the_pupicides_only_go_on_the_lagoon(stocked: Book) -> None:
    for one in products.all_products(stocked, purpose="pupicide"):
        assert one.labelled_habitats() == ["lagoon"]


def test_only_one_product_is_restricted(stocked: Book) -> None:
    restricted = [one.name for one in products.all_products(stocked) if one.restricted]
    assert restricted == ["Kestrel ULV"]


def test_the_briquet_lasts_most_of_a_season(stocked: Book) -> None:
    found = products.find_by_name(stocked, "Hesper 30 briquets")
    assert found is not None
    entry = found.label_for("catch_basin")
    assert entry is not None
    assert entry.interval_days >= 120


def test_the_same_active_appears_at_two_strengths(stocked: Book) -> None:
    both = products.all_products(
        stocked,
        active="Bacillus thuringiensis subspecies israelensis",
    )
    assert len(both) == 2
    assert {one.percent for one in both} == {4.5, 37}


def test_a_strong_product_carries_more_active_at_the_same_weight(stocked: Book) -> None:
    weak = products.find_by_name(stocked, "Bactilore G")
    strong = products.find_by_name(stocked, "Bactilore WSP")
    assert weak is not None
    assert strong is not None
    assert strong.active_in(quantity("1 lb")) > weak.active_in(quantity("1 lb"))


def test_an_entry_is_found_by_name() -> None:
    assert formulary.entry("Bactilore G").purpose == LARVICIDE
    with pytest.raises(NotFound):
        formulary.entry("Nothing at all")


def test_the_season_cap_can_be_asked_for_directly() -> None:
    assert formulary.season_cap("Bactilore G", "lagoon") == quantity("80 lb")
    assert formulary.season_cap("Bactilore G", "container") is None


def test_the_actives_on_the_starting_shelf_are_listed() -> None:
    assert "spinosad" in formulary.actives()
    assert len(formulary.actives()) >= 6
