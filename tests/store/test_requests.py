from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock
from dipcount.errors import NotFound, RuleViolation
from dipcount.model.applicator import CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.request import BITING, DEAD_BIRD
from dipcount.store import Book, applicators, requests, sites, upgrade, zones
from dipcount.units import quantity

TAKEN = clock.moment("2025-07-08 09:15")


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), dt.date(2025, 3, 1))
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    return book


def call(book: Book, kind: str = BITING, zone: str = "north") -> str:
    return requests.take(book, kind, zone, TAKEN, "1400 Weir Street", caller="A. Sandoval").id


def test_a_call_is_numbered_and_read_back(district: Book) -> None:
    made = call(district)
    assert made == "SR-0001"
    assert requests.get(district, made).caller == "A. Sandoval"


def test_a_call_under_a_zone_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        requests.take(district, BITING, "east", TAKEN, "nowhere")


def test_somebody_is_put_against_a_call(district: Book) -> None:
    made = call(district)
    after = requests.assign(district, made, "AP-001")
    assert after.assigned_to == "AP-001"
    assert [one.id for one in requests.for_applicator(district, "AP-001")] == [made]


def test_a_visit_is_recorded_with_the_site_it_found(district: Book) -> None:
    made = call(district)
    after = requests.visit(
        district,
        made,
        clock.moment("2025-07-09 10:00"),
        site_id="SI-0001",
    )
    assert after.visited
    assert after.site == "SI-0001"
    assert [one.id for one in requests.for_site(district, "SI-0001")] == [made]


def test_a_call_is_not_visited_twice(district: Book) -> None:
    made = call(district)
    requests.visit(district, made, clock.moment("2025-07-09 10:00"))
    with pytest.raises(RuleViolation, match="visited already"):
        requests.visit(district, made, clock.moment("2025-07-10 10:00"))


def test_a_visit_before_the_call_is_refused(district: Book) -> None:
    made = call(district)
    with pytest.raises(RuleViolation):
        requests.visit(district, made, clock.moment("2025-07-07 10:00"))


def test_a_visit_to_a_site_that_is_not_there(district: Book) -> None:
    made = call(district)
    with pytest.raises(NotFound):
        requests.visit(district, made, clock.moment("2025-07-09 10:00"), site_id="SI-0099")


def test_a_call_is_closed_with_an_outcome(district: Book) -> None:
    made = call(district)
    after = requests.close(district, made, clock.moment("2025-07-09 16:00"), "basins treated")
    assert not after.open
    assert after.outcome == "basins treated"


def test_a_call_is_not_closed_twice(district: Book) -> None:
    made = call(district)
    requests.close(district, made, clock.moment("2025-07-09 16:00"), "basins treated")
    with pytest.raises(RuleViolation, match="was closed"):
        requests.close(district, made, clock.moment("2025-07-10 16:00"), "again")


def test_a_closed_call_takes_no_more_work(district: Book) -> None:
    made = call(district)
    requests.close(district, made, clock.moment("2025-07-09 16:00"), "nothing found")
    with pytest.raises(RuleViolation):
        requests.assign(district, made, "AP-001")
    with pytest.raises(RuleViolation):
        requests.visit(district, made, clock.moment("2025-07-10 10:00"))


def test_closing_with_no_outcome_is_refused(district: Book) -> None:
    made = call(district)
    with pytest.raises(RuleViolation, match="outcome"):
        requests.close(district, made, clock.moment("2025-07-09 16:00"), "  ")


def test_calls_narrow_by_zone_and_kind(district: Book) -> None:
    call(district)
    call(district, kind=DEAD_BIRD)
    call(district, zone="south")
    assert len(requests.all_requests(district)) == 3
    assert len(requests.all_requests(district, zone_id="ZN-001")) == 2
    assert len(requests.all_requests(district, kind=DEAD_BIRD)) == 1


def test_the_open_and_unvisited_lists_are_different(district: Book) -> None:
    first = call(district)
    second = call(district)
    requests.visit(district, first, clock.moment("2025-07-09 10:00"))
    assert len(requests.open_calls(district)) == 2
    assert [one.id for one in requests.unvisited(district)] == [second]


def test_a_closed_call_leaves_both_lists(district: Book) -> None:
    made = call(district)
    requests.close(district, made, clock.moment("2025-07-09 16:00"), "nothing found")
    assert requests.open_calls(district) == []
    assert requests.unvisited(district) == []


def test_a_window_and_a_week_gather_the_calls(district: Book) -> None:
    call(district)
    requests.take(district, BITING, "north", clock.moment("2025-07-20 09:00"), "elsewhere")
    assert len(requests.between(district, dt.date(2025, 7, 1), dt.date(2025, 7, 10))) == 1
    assert len(requests.in_week(district, 2025, 28)) == 1


def test_a_missing_call(district: Book) -> None:
    with pytest.raises(NotFound):
        requests.get(district, "SR-0099")
