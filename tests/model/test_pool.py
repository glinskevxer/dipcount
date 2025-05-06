from __future__ import annotations

import datetime as dt

import pytest

from dipcount import species
from dipcount.errors import NotFound, UsageError
from dipcount.model.pool import (
    MAX_POOL,
    NEGATIVE,
    PENDING,
    POSITIVE,
    UNSATISFACTORY,
    Assay,
    Pool,
)

SUBMITTED = dt.date(2025, 6, 5)
TESTED = dt.date(2025, 6, 9)


def a_pool(**changes: object) -> Pool:
    fields: dict[str, object] = {
        "id": "PL-250605-01",
        "collection": "CO-250604-01",
        "species": "CXPP",
        "size": 50,
        "submitted_on": SUBMITTED,
    }
    fields.update(changes)
    return Pool(**fields)  # type: ignore[arg-type]


def test_a_pool_holds_one_species_the_district_knows() -> None:
    assert a_pool().sort.binomial == "Culex pipiens"
    with pytest.raises(NotFound):
        a_pool(species="ZZZZ")


def test_a_pool_of_nothing_is_not_a_pool() -> None:
    with pytest.raises(UsageError):
        a_pool(size=0)


def test_the_laboratory_will_not_take_more_than_fifty() -> None:
    assert a_pool(size=MAX_POOL).size == 50
    with pytest.raises(UsageError, match="laboratory"):
        a_pool(size=MAX_POOL + 1)


def test_an_assay_takes_a_virus_the_district_tests_for() -> None:
    assert Assay(species.WNV, NEGATIVE, TESTED).virus == species.WNV
    with pytest.raises(UsageError):
        Assay("influenza", NEGATIVE, TESTED)


def test_an_unknown_outcome_is_refused() -> None:
    with pytest.raises(UsageError):
        Assay(species.WNV, "maybe", TESTED)


def test_a_pending_result_has_not_been_tested() -> None:
    assert Assay(species.WNV, PENDING).tested_on is None
    with pytest.raises(UsageError, match="pending"):
        Assay(species.WNV, PENDING, TESTED)


def test_a_finished_result_carries_the_day_it_was_run() -> None:
    with pytest.raises(UsageError, match="needs the day"):
        Assay(species.WNV, NEGATIVE)


def test_only_a_positive_carries_a_cycle_threshold() -> None:
    assert Assay(species.WNV, POSITIVE, TESTED, ct=28.4).ct == 28.4
    with pytest.raises(UsageError, match="cycle threshold"):
        Assay(species.WNV, NEGATIVE, TESTED, ct=28.4)


def test_an_unsatisfactory_pool_is_neither_positive_nor_negative() -> None:
    bad = Assay(species.WNV, UNSATISFACTORY, TESTED)
    assert not bad.counts
    assert Assay(species.WNV, NEGATIVE, TESTED).counts
    assert Assay(species.WNV, POSITIVE, TESTED).counts
    assert not Assay(species.WNV, PENDING).counts


def test_a_pool_cannot_hold_two_results_for_one_virus() -> None:
    with pytest.raises(UsageError, match="two results"):
        a_pool(
            assays=(
                Assay(species.WNV, NEGATIVE, TESTED),
                Assay(species.WNV, POSITIVE, TESTED),
            ),
        )


def test_a_virus_never_run_reads_as_pending() -> None:
    pool = a_pool(assays=(Assay(species.WNV, NEGATIVE, TESTED),))
    assert pool.outcome(species.WNV) == NEGATIVE
    assert pool.outcome(species.EEE) == PENDING
    assert pool.result(species.EEE) is None


def test_one_virus_back_and_another_still_out_is_an_ordinary_record() -> None:
    pool = a_pool(assays=(Assay(species.WNV, POSITIVE, TESTED, ct=27.1),))
    assert pool.is_positive(species.WNV)
    assert not pool.is_positive(species.EEE)
    assert pool.counts_for(species.WNV)
    assert not pool.counts_for(species.EEE)


def test_a_pool_of_something_that_carries_nothing_is_still_a_pool() -> None:
    vexans = a_pool(species="AEVX", assays=(Assay(species.WNV, NEGATIVE, TESTED),))
    assert not vexans.could_carry(species.WNV)
    assert vexans.counts_for(species.WNV)


def test_the_culex_could_carry_west_nile() -> None:
    assert a_pool().could_carry(species.WNV)
    assert not a_pool().could_carry(species.EEE)


def test_the_row_is_what_the_book_stores() -> None:
    row = a_pool().to_row()
    assert row["size"] == 50
    assert row["submitted_on"] == "2025-06-05"
