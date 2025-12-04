from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, species
from dipcount.model.pool import POSITIVE
from dipcount.model.request import BITING, DEAD_BIRD, SPRAY
from dipcount.model.trap import Catch
from dipcount.service import requests as service
from dipcount.store import Book, audit, pools, requests, traps, upgrade, zones

TAKEN = clock.moment("2025-07-08 09:15")
OFFICE = "T. Okwuosa"


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    traps.add(book, "north", "Ambrose gravid 1", "gravid", dt.date(2025, 4, 1))
    return book


def busy_week(book: Book) -> None:
    """Put the north zone on a high response level in the week of the eighth."""
    made = traps.record(
        book,
        "TR-0001",
        clock.moment("2025-07-06 16:30"),
        clock.moment("2025-07-07 08:15"),
        "D. Uzoma",
        catches=[Catch("CXPP", "F", 400)],
    )
    for _ in range(4):
        pool = pools.submit(book, made.id, "CXPP", 50, dt.date(2025, 7, 8))
        pools.report(book, pool.id, species.WNV, POSITIVE, dt.date(2025, 7, 9))


def call(book: Book, kind: str = BITING, zone: str = "north") -> str:
    return service.take(book, OFFICE, kind, zone, TAKEN, "1400 Weir Street").id


def test_taking_a_call_leaves_a_line(district: Book) -> None:
    made = call(district)
    lines = audit.about(district, made)
    assert [one.action for one in lines] == ["took call"]


def test_a_quiet_season_leaves_the_clock_alone(district: Book) -> None:
    made = call(district, kind=DEAD_BIRD)
    where = service.standing(district, made, clock.moment("2025-07-08 12:00"))
    assert where.hours == 24
    assert not where.escalated
    assert where.level == "none"


def test_a_busy_week_halves_the_dead_bird_clock(district: Book) -> None:
    busy_week(district)
    made = call(district, kind=DEAD_BIRD)
    where = service.standing(district, made, clock.moment("2025-07-08 12:00"))
    assert where.escalated
    assert where.hours == 12
    assert where.level in {"high", "emergency"}
    assert "cut from 24" in where.line()


def test_a_busy_week_halves_the_spray_concern_clock(district: Book) -> None:
    busy_week(district)
    made = call(district, kind=SPRAY)
    assert service.standing(district, made, TAKEN).hours == 12


def test_a_busy_week_leaves_the_biting_clock_where_it_was(district: Book) -> None:
    busy_week(district)
    made = call(district, kind=BITING)
    where = service.standing(district, made, TAKEN)
    assert where.hours == 72
    assert not where.escalated


def test_the_escalation_reads_the_zone_the_call_came_from(district: Book) -> None:
    busy_week(district)
    north = call(district, kind=DEAD_BIRD, zone="north")
    south = call(district, kind=DEAD_BIRD, zone="south")
    assert service.standing(district, north, TAKEN).escalated
    assert not service.standing(district, south, TAKEN).escalated


def test_a_call_answered_inside_the_shortened_clock(district: Book) -> None:
    busy_week(district)
    made = call(district, kind=DEAD_BIRD)
    where = service.answer(district, OFFICE, made, clock.moment("2025-07-08 17:00"))
    assert not where.late
    assert where.request.answered_in() == Decimal("7.75")


def test_the_same_answer_would_have_been_late_at_twelve_hours(district: Book) -> None:
    busy_week(district)
    made = call(district, kind=DEAD_BIRD)
    where = service.answer(district, OFFICE, made, clock.moment("2025-07-08 23:00"))
    assert where.late
    quiet = requests.take(district, DEAD_BIRD, "south", TAKEN, "elsewhere")
    requests.visit(district, quiet.id, clock.moment("2025-07-08 23:00"))
    assert not service.standing(district, quiet.id, TAKEN).late


def test_answering_leaves_a_line_saying_whether_it_was_in_time(district: Book) -> None:
    made = call(district)
    service.answer(district, OFFICE, made, clock.moment("2025-07-09 09:00"))
    lines = [one for one in audit.about(district, made) if one.action == "answered call"]
    assert "in time" in lines[0].detail


def test_closing_leaves_the_outcome_on_the_trail(district: Book) -> None:
    made = call(district)
    service.answer(district, OFFICE, made, clock.moment("2025-07-09 09:00"))
    service.finish(district, OFFICE, made, clock.moment("2025-07-09 16:00"), "ditch treated")
    lines = [one for one in audit.about(district, made) if one.action == "closed call"]
    assert lines[0].detail == "ditch treated"


def test_the_waiting_list_puts_the_tightest_clock_first(district: Book) -> None:
    slow = call(district, kind=BITING)
    fast = call(district, kind=DEAD_BIRD)
    found = service.waiting(district, clock.moment("2025-07-08 12:00"))
    assert [one.request.id for one in found] == [fast, slow]


def test_an_answered_call_leaves_the_waiting_list(district: Book) -> None:
    made = call(district)
    call(district, kind=DEAD_BIRD)
    service.answer(district, OFFICE, made, clock.moment("2025-07-08 12:00"))
    found = service.waiting(district, clock.moment("2025-07-08 13:00"))
    assert [one.request.id for one in found] == ["SR-0002"]


def test_what_has_run_out_of_time_is_named(district: Book) -> None:
    call(district, kind=DEAD_BIRD)
    call(district, kind=BITING)
    late = service.overdue(district, clock.moment("2025-07-09 12:00"))
    assert [one.request.id for one in late] == ["SR-0001"]


def test_the_waiting_list_narrows_to_a_zone(district: Book) -> None:
    call(district, zone="north")
    call(district, zone="south")
    found = service.waiting(district, clock.moment("2025-07-08 12:00"), zone_id="ZN-002")
    assert [one.request.id for one in found] == ["SR-0002"]


def test_performance_counts_what_was_answered_in_time(district: Book) -> None:
    early = call(district, kind=BITING)
    late = call(district, kind=DEAD_BIRD)
    service.answer(district, OFFICE, early, clock.moment("2025-07-09 09:00"))
    service.answer(district, OFFICE, late, clock.moment("2025-07-11 09:00"))
    found = service.performance(district, dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert found.taken == 2
    assert found.answered == 2
    assert found.on_time == 1
    assert found.share_on_time == Decimal("0.5")
    assert "50% in time" in found.line()


def test_performance_with_nothing_answered(district: Book) -> None:
    call(district)
    found = service.performance(district, dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert found.answered == 0
    assert found.share_on_time == 0
    assert found.median_hours is None
    assert "no answers" in found.line()


def test_the_median_answer_time_is_reported(district: Book) -> None:
    first = call(district)
    second = call(district)
    service.answer(district, OFFICE, first, clock.moment("2025-07-08 19:15"))
    service.answer(district, OFFICE, second, clock.moment("2025-07-09 09:15"))
    found = service.performance(district, dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert found.median_hours == Decimal("17")


def test_a_call_visited_late_stays_late_in_the_standing(district: Book) -> None:
    made = call(district, kind=DEAD_BIRD)
    service.answer(district, OFFICE, made, clock.moment("2025-07-12 09:00"))
    where = service.standing(district, made, clock.moment("2025-08-01 09:00"))
    assert where.late
    assert "late" in where.line()
