from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock, species
from dipcount.errors import Duplicate, NotFound, RuleViolation
from dipcount.model.pool import NEGATIVE, PENDING, POSITIVE, UNSATISFACTORY
from dipcount.model.trap import Catch
from dipcount.store import Book, traps, upgrade, zones
from dipcount.store import pools as store

LISTED = dt.date(2025, 4, 1)
SUBMITTED = dt.date(2025, 6, 5)
TESTED = dt.date(2025, 6, 9)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    traps.record(
        book,
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        "D. Uzoma",
        catches=[Catch("CXPP", "F", 120), Catch("CXPP", "M", 40), Catch("AEVX", "F", 10)],
    )
    return book


def test_a_pool_is_numbered_by_the_day_it_was_sent(district: Book) -> None:
    made = store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED, lab="state health")
    assert made.id == "PL-250605-01"
    assert made.size == 50


def test_pools_out_of_one_jar_cannot_exceed_what_was_in_it(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    with pytest.raises(RuleViolation, match="too many"):
        store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    assert store.pooled(district, "CO-250604-01", "CXPP") == 100


def test_the_remainder_of_a_jar_can_still_go(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    made = store.submit(district, "CO-250604-01", "CXPP", 20, SUBMITTED)
    assert made.size == 20


def test_each_species_has_its_own_limit(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    made = store.submit(district, "CO-250604-01", "AEVX", 10, SUBMITTED)
    assert made.species == "AEVX"
    with pytest.raises(RuleViolation):
        store.submit(district, "CO-250604-01", "AEVX", 1, SUBMITTED)


def test_males_are_not_available_to_pool(district: Book) -> None:
    with pytest.raises(RuleViolation, match="120 female"):
        store.submit(district, "CO-250604-01", "CXPP", 121, SUBMITTED)


def test_a_species_never_in_the_jar_cannot_be_pooled(district: Book) -> None:
    with pytest.raises(RuleViolation):
        store.submit(district, "CO-250604-01", "CXTR", 1, SUBMITTED)


def test_an_unknown_species_is_refused(district: Book) -> None:
    with pytest.raises(NotFound):
        store.submit(district, "CO-250604-01", "ZZZZ", 1, SUBMITTED)


def test_a_pool_off_a_collection_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        store.submit(district, "CO-250604-09", "CXPP", 50, SUBMITTED)


def test_a_result_is_written_against_a_pool(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    after = store.report(district, "PL-250605-01", species.WNV, POSITIVE, TESTED, ct=27.4)
    assert after.is_positive(species.WNV)
    assert after.outcome(species.EEE) == PENDING


def test_two_results_for_one_virus_are_refused(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.report(district, "PL-250605-01", species.WNV, NEGATIVE, TESTED)
    with pytest.raises(Duplicate):
        store.report(district, "PL-250605-01", species.WNV, POSITIVE, TESTED)


def test_two_viruses_on_one_pool_are_kept_apart(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.report(district, "PL-250605-01", species.WNV, POSITIVE, TESTED, ct=27.4)
    after = store.report(district, "PL-250605-01", species.SLE, NEGATIVE, TESTED)
    assert after.is_positive(species.WNV)
    assert not after.is_positive(species.SLE)
    assert len(after.assays) == 2


def test_a_bad_result_writes_nothing(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    with pytest.raises(Exception, match="cycle threshold"):
        store.report(district, "PL-250605-01", species.WNV, NEGATIVE, TESTED, ct=27.4)
    assert district.count("assay") == 0


def test_the_pools_off_one_jar_are_listed(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    assert len(store.for_collection(district, "CO-250604-01")) == 2


def test_a_window_takes_the_pools_sent_in_it(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.submit(district, "CO-250604-01", "CXPP", 50, dt.date(2025, 6, 20))
    found = store.submitted_between(district, dt.date(2025, 6, 1), dt.date(2025, 6, 10))
    assert len(found) == 1


def test_a_week_gathers_the_pools_sent_in_it(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    assert len(store.in_week(district, 2025, 23)) == 1
    assert len(store.in_week(district, 2025, 24)) == 0


def test_what_is_still_out_at_the_lab_is_named(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.report(district, "PL-250605-01", species.WNV, NEGATIVE, TESTED)
    waiting = store.outstanding(district, species.WNV)
    assert [one.id for one in waiting] == ["PL-250605-02"]


def test_an_unsatisfactory_pool_is_no_longer_outstanding(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.report(district, "PL-250605-01", species.WNV, UNSATISFACTORY, TESTED)
    assert store.outstanding(district, species.WNV) == []


def test_the_positives_for_a_virus_come_back(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    store.report(district, "PL-250605-01", species.WNV, POSITIVE, TESTED, ct=27.4)
    store.report(district, "PL-250605-02", species.WNV, NEGATIVE, TESTED)
    found = store.positive_between(district, species.WNV, SUBMITTED, SUBMITTED)
    assert [one.id for one in found] == ["PL-250605-01"]


def test_the_labs_are_listed(district: Book) -> None:
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED, lab="state health")
    store.submit(district, "CO-250604-01", "CXPP", 50, SUBMITTED)
    assert store.labs(district) == ["state health"]
