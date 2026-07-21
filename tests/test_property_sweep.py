"""Sweeping the arithmetic rather than checking one worked example.

A worked example proves the code gets that example right. What these ask is
whether the relationships hold: does converting back give what went in, does
adding two quantities give the same answer either way round, does the
estimated infection rate always sit above the minimum one. Those are the
properties somebody would state if asked what the code is for, and a change
that breaks one of them is a change that got the domain wrong rather than a
number wrong.

Everything here is deterministic. A sweep that picks its own inputs at random
fails on a Tuesday and passes on a Wednesday, and nobody ever finds out which
input it was.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from itertools import pairwise

import pytest

from dipcount import estimate, ids
from dipcount.units import MASS, VOLUME, Quantity, Rate, quantity, rate, units_in

MASSES = units_in(MASS)
VOLUMES = units_in(VOLUME)
AMOUNTS = [Decimal("0.25"), Decimal(1), Decimal(7), Decimal("12.5"), Decimal(400)]


def test_every_conversion_round_trips_to_where_it_started() -> None:
    for unit in MASSES + VOLUMES:
        for other in MASSES if unit in MASSES else VOLUMES:
            for amount in AMOUNTS:
                one = Quantity(amount, unit)
                assert one.to(other).to(unit).rounded(9) == one.rounded(9)


def test_addition_gives_the_same_answer_either_way_round() -> None:
    for unit in MASSES:
        for other in MASSES:
            left = Quantity(Decimal(3), unit)
            right = Quantity(Decimal(5), other)
            assert (left + right).to("g").rounded(9) == (right + left).to("g").rounded(9)


def test_adding_and_taking_back_off_leaves_what_went_in() -> None:
    for unit in VOLUMES:
        one = Quantity(Decimal(9), unit)
        other = quantity("2 fl oz")
        assert ((one + other) - other).rounded(9) == one.rounded(9)


def test_a_ratio_and_its_inverse_multiply_to_one() -> None:
    for unit in MASSES:
        one = Quantity(Decimal(4), unit)
        other = quantity("3 lb")
        assert (one.ratio(other) * other.ratio(one)).quantize(Decimal("1.000000")) == Decimal(1)


def test_ordering_survives_a_conversion() -> None:
    for unit in MASSES:
        for other in MASSES:
            small = Quantity(Decimal(1), unit)
            large = Quantity(Decimal(1000), unit)
            assert small.to(other) < large.to(other)


def test_a_rate_over_twice_the_ground_puts_on_twice_as_much() -> None:
    for text in ("2.5 lb/acre", "8 fl oz/acre", "1 each/each"):
        one = rate(text)
        unit = one.per
        single = one.over(Quantity(Decimal(3), unit))
        double = one.over(Quantity(Decimal(6), unit))
        assert double.amount == single.amount * 2


def test_a_rate_written_in_another_unit_puts_on_the_same_amount() -> None:
    one = rate("8 fl oz/acre")
    ground = quantity("4 acre")
    for unit in VOLUMES:
        moved = Rate(one.amount.to(unit), one.per)
        assert moved.over(ground).to("fl oz").rounded(6) == one.over(ground).rounded(6)


def test_the_estimate_never_reads_under_the_minimum_rate() -> None:
    sizes = [50] * 20
    for hits in range(21):
        outcomes = [True] * hits + [False] * (20 - hits)
        found = estimate.estimate(sizes, outcomes)
        floor = estimate.minimum_infection_rate(sizes, outcomes)
        assert found.rate >= floor


def test_the_estimate_climbs_with_every_extra_positive() -> None:
    sizes = [50] * 20
    rates = [
        estimate.estimate(sizes, [True] * hits + [False] * (20 - hits)).rate for hits in range(21)
    ]
    for one, following in pairwise(rates):
        assert following > one


def test_the_interval_brackets_the_estimate_at_every_count() -> None:
    sizes = [50] * 20
    for hits in range(1, 20):
        found = estimate.estimate(sizes, [True] * hits + [False] * (20 - hits))
        assert found.lower <= found.rate <= found.upper


def test_the_order_the_pools_come_back_in_changes_nothing() -> None:
    sizes = [50, 30, 12, 44, 8]
    outcomes = [True, False, True, False, False]
    forwards = estimate.estimate(sizes, outcomes)
    backwards = estimate.estimate(sizes[::-1], outcomes[::-1])
    assert forwards.rate == backwards.rate
    assert forwards.lower == backwards.lower


def test_more_pools_at_the_same_share_narrow_the_interval() -> None:
    widths = []
    for many in (10, 20, 40, 80):
        outcomes = [True] * (many // 10) + [False] * (many - many // 10)
        found = estimate.estimate([50] * many, outcomes)
        widths.append(found.upper - found.lower)
    for one, following in pairwise(widths):
        assert following < one


@pytest.mark.parametrize("kind", ["site", "trap", "product", "lot", "block"])
def test_minting_a_long_run_of_serials_never_repeats(kind: str) -> None:
    taken: list[str] = []
    for _ in range(200):
        taken.append(ids.next_serial(kind, taken))
    assert len(set(taken)) == 200
    assert all(ids.looks_like(kind, one) for one in taken)


def test_minting_a_day_of_dated_ids_never_repeats() -> None:
    for kind in ("dip", "collection", "treatment", "run"):
        taken: list[str] = []
        for _ in range(99):
            taken.append(ids.next_dated(kind, dt.date(2025, 6, 4), taken))
        assert len(set(taken)) == 99
        assert all(ids.day_of(one) == dt.date(2025, 6, 4) for one in taken)


def test_every_id_reads_back_as_the_kind_it_was_minted_as() -> None:
    for kind in ("site", "trap", "product", "lot", "block"):
        assert ids.kind_from(ids.next_serial(kind, [])) == kind
    for kind in ("dip", "collection", "treatment", "run"):
        assert ids.kind_from(ids.next_dated(kind, dt.date(2025, 6, 4), [])) == kind
