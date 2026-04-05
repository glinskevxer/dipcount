from __future__ import annotations

from decimal import Decimal

import pytest

from dipcount.errors import UsageError
from dipcount.units import (
    AREA,
    MASS,
    VOLUME,
    Quantity,
    Rate,
    canonical,
    dimension_of,
    quantity,
    rate,
    units_in,
)


def test_an_ounce_is_mass_and_a_fluid_ounce_is_volume() -> None:
    assert dimension_of("oz") == MASS
    assert dimension_of("fl oz") == VOLUME


def test_the_two_ounces_do_not_convert_into_each_other() -> None:
    with pytest.raises(UsageError):
        quantity("8 fl oz").to("oz")


def test_aliases_fold_to_one_spelling() -> None:
    assert canonical("gallons") == "gal"
    assert canonical("ML") == "mL"
    assert canonical("Acres") == "acre"
    assert canonical("lbs") == "lb"


def test_an_unknown_unit_is_refused() -> None:
    with pytest.raises(UsageError):
        canonical("hogshead")


def test_units_in_a_dimension_are_listed() -> None:
    assert "acre" in units_in(AREA)
    assert "oz" not in units_in(AREA)


def test_parsing_takes_an_amount_and_a_unit() -> None:
    q = quantity("8 fl oz")
    assert q.amount == Decimal("8")
    assert q.unit == "fl oz"


def test_an_amount_without_a_unit_is_not_a_quantity() -> None:
    with pytest.raises(UsageError):
        quantity("8")
    with pytest.raises(UsageError):
        quantity("plenty of it")


def test_conversion_within_a_dimension() -> None:
    assert quantity("1 gal").to("fl oz").amount == Decimal("128")
    assert quantity("1 lb").to("oz").amount == Decimal("16")
    assert quantity("1 acre").to("ft2").rounded(0).amount == Decimal("43560")


def test_a_conversion_round_trips_to_itself() -> None:
    q = quantity("6.5 acre")
    assert q.to("ha").to("acre").rounded(6) == q.rounded(6)


def test_addition_uses_the_left_hand_unit() -> None:
    total = quantity("1 qt") + quantity("8 fl oz")
    assert total.unit == "qt"
    assert total.to("fl oz").amount == Decimal("40")


def test_subtraction_can_go_negative() -> None:
    left = quantity("4 fl oz") - quantity("1 pt")
    assert left.amount < 0


def test_adding_across_dimensions_is_refused() -> None:
    with pytest.raises(UsageError):
        _ = quantity("4 fl oz") + quantity("2 acre")


def test_a_quantity_scales_and_divides() -> None:
    assert (quantity("2 fl oz") * 3).amount == Decimal("6")
    assert (quantity("9 lb") / 3).amount == Decimal("3")
    with pytest.raises(UsageError):
        _ = quantity("9 lb") / 0


def test_ratio_is_a_plain_number() -> None:
    assert quantity("1 gal").ratio(quantity("1 qt")) == Decimal("4")
    with pytest.raises(UsageError):
        quantity("1 gal").ratio(quantity("1 acre"))
    with pytest.raises(UsageError):
        quantity("1 gal").ratio(quantity("0 qt"))


def test_quantities_compare_across_units() -> None:
    assert quantity("1 gal") > quantity("100 fl oz")
    assert quantity("1 qt") <= quantity("32 fl oz")
    assert quantity("32 fl oz") >= quantity("1 qt")
    assert quantity("1 pt") < quantity("1 qt")


def test_printing_drops_trailing_zeros() -> None:
    assert str(quantity("8.500 fl oz")) == "8.5 fl oz"
    assert str(quantity("6 acre")) == "6 acre"


def test_a_rate_applies_over_ground() -> None:
    applied = rate("8 fl oz/acre").over(quantity("2.5 acre"))
    assert applied.to("fl oz").amount == Decimal("20")


def test_a_rate_reads_the_word_per() -> None:
    assert Rate.parse("1 each per basin".replace("basin", "each")).per == "each"
    assert rate("0.5 lb per acre").amount.unit == "lb"


def test_a_rate_needs_a_denominator() -> None:
    with pytest.raises(UsageError):
        rate("8 fl oz")
    with pytest.raises(UsageError):
        rate("8 fl oz/")


def test_a_per_acre_rate_refuses_a_volume_extent() -> None:
    with pytest.raises(UsageError):
        rate("8 fl oz/acre").over(quantity("40 gal"))


def test_a_rate_converts_both_halves() -> None:
    moved = rate("8 fl oz/acre").to("mL", "ha")
    assert moved.per == "ha"
    assert moved.amount.unit == "mL"
    over_ten = moved.over(quantity("10 ha"))
    same = rate("8 fl oz/acre").over(quantity("10 ha").to("acre"))
    assert over_ten.to("mL").rounded(4) == same.to("mL").rounded(4)


def test_a_rate_prints_the_way_a_label_reads() -> None:
    assert str(rate("8 fl oz/acre")) == "8 fl oz/acre"


def test_a_quantity_accepts_a_float_amount() -> None:
    assert Quantity(Decimal("2.5"), "acre").amount == Decimal("2.5")
    assert Quantity(Decimal(2), "acre").dimension == AREA
