from __future__ import annotations

from decimal import Decimal

import pytest

from dipcount import estimate as est
from dipcount.errors import UsageError


def test_nothing_tested_gives_nothing() -> None:
    found = est.estimate([], [])
    assert not found.usable
    assert found.rate == 0
    assert found.line() == "no pools tested"


def test_the_minimum_rate_is_positives_over_mosquitoes() -> None:
    rate = est.minimum_infection_rate([50] * 10, [True] + [False] * 9)
    assert rate == Decimal(2)


def test_the_minimum_rate_of_nothing_positive_is_zero() -> None:
    assert est.minimum_infection_rate([50] * 10, [False] * 10) == 0


def test_the_likelihood_estimate_is_above_the_minimum() -> None:
    sizes = [50] * 10
    hits = [True] + [False] * 9
    found = est.estimate(sizes, hits)
    assert found.rate > est.minimum_infection_rate(sizes, hits)
    assert float(found.rate) == pytest.approx(2.1053, abs=0.001)


def test_the_gap_between_the_two_widens_as_infection_climbs() -> None:
    sizes = [50] * 10
    near = est.estimate(sizes, [True] + [False] * 9)
    far = est.estimate(sizes, [True] * 8 + [False] * 2)
    near_gap = near.rate - est.minimum_infection_rate(sizes, [True] + [False] * 9)
    far_gap = far.rate - est.minimum_infection_rate(sizes, [True] * 8 + [False] * 2)
    assert far_gap > near_gap


def test_no_positives_estimates_a_rate_of_nothing() -> None:
    found = est.estimate([50] * 20, [False] * 20)
    assert found.rate == 0
    assert found.lower == 0
    assert found.upper > 0


def test_every_pool_positive_pins_the_estimate_at_the_top() -> None:
    found = est.estimate([50] * 5, [True] * 5)
    assert found.rate == Decimal(1000)
    assert found.upper == Decimal(1000)
    assert found.lower < Decimal(1000)


def test_the_interval_brackets_the_estimate() -> None:
    found = est.estimate([50] * 20, [True, True] + [False] * 18)
    assert found.lower < found.rate < found.upper


def test_more_pools_narrow_the_interval() -> None:
    few = est.estimate([50] * 10, [True] + [False] * 9)
    many = est.estimate([50] * 100, [True] * 10 + [False] * 90)
    assert (many.upper - many.lower) < (few.upper - few.lower)
    assert float(many.rate) == pytest.approx(float(few.rate), abs=0.01)


def test_pools_of_different_sizes_are_handled() -> None:
    found = est.estimate([50, 30, 12, 44, 8], [True, False, False, False, False])
    assert found.mosquitoes == 144
    assert found.pools == 5
    assert found.rate > 0


def test_a_positive_in_a_small_pool_says_more_than_one_in_a_big_pool() -> None:
    small = est.estimate([5] + [50] * 9, [True] + [False] * 9)
    large = est.estimate([50] * 10, [True] + [False] * 9)
    assert small.rate > large.rate


def test_the_estimate_counts_what_it_was_given() -> None:
    found = est.estimate([50] * 10, [True, True] + [False] * 8)
    assert found.pools == 10
    assert found.positives == 2
    assert found.mosquitoes == 500
    assert "2 of 10 pools" in found.line()


def test_a_pool_of_nothing_cannot_be_tested() -> None:
    with pytest.raises(UsageError):
        est.estimate([0], [False])
    with pytest.raises(UsageError):
        est.minimum_infection_rate([-1], [False])


def test_sizes_and_outcomes_have_to_match_up() -> None:
    with pytest.raises(UsageError):
        est.estimate([50, 50], [True])


def test_the_rate_climbs_with_the_share_of_positive_pools() -> None:
    sizes = [50] * 20
    rates = [est.estimate(sizes, [True] * hits + [False] * (20 - hits)).rate for hits in range(20)]
    assert rates == sorted(rates)
    assert len(set(rates)) == len(rates)


def test_the_vector_index_is_abundance_times_rate() -> None:
    assert est.vector_index(Decimal(40), Decimal(5)) == Decimal("0.2")
    assert est.vector_index(Decimal(0), Decimal(5)) == 0


def test_a_negative_vector_index_is_refused() -> None:
    with pytest.raises(UsageError):
        est.vector_index(Decimal(-1), Decimal(5))
    with pytest.raises(UsageError):
        est.vector_index(Decimal(1), Decimal(-5))
