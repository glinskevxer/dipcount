from __future__ import annotations

from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.model.request import (
    BITING,
    DEAD_BIRD,
    OTHER,
    SPRAY,
    WATER,
    Request,
    answer_hours,
    kinds,
    why,
)

TAKEN = clock.moment("2025-07-08 09:15")


def a_call(**changes: object) -> Request:
    fields: dict[str, object] = {
        "id": "SR-0001",
        "kind": BITING,
        "zone": "ZN-001",
        "taken_at": TAKEN,
        "address": "1400 Weir Street",
    }
    fields.update(changes)
    return Request(**fields)  # type: ignore[arg-type]


def test_every_kind_has_an_answer_time_and_a_reason() -> None:
    for kind in kinds():
        assert answer_hours(kind) > 0
        assert why(kind)


def test_the_kinds_come_back_fastest_first() -> None:
    times = [answer_hours(kind) for kind in kinds()]
    assert times == sorted(times)


def test_a_dead_bird_is_answered_before_a_biting_complaint() -> None:
    assert answer_hours(DEAD_BIRD) < answer_hours(BITING)
    assert "decays" in why(DEAD_BIRD)


def test_a_spray_concern_is_answered_the_same_day() -> None:
    assert answer_hours(SPRAY) == 24


def test_anything_else_waits_the_longest() -> None:
    assert answer_hours(OTHER) == max(answer_hours(kind) for kind in kinds())


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(UsageError):
        answer_hours("noise complaint")
    with pytest.raises(UsageError):
        a_call(kind="noise complaint")


def test_a_call_needs_somewhere_to_go_and_a_zone_on_its_moment() -> None:
    with pytest.raises(UsageError):
        a_call(address=" ")
    with pytest.raises(UsageError):
        a_call(taken_at=TAKEN.replace(tzinfo=None))


def test_the_due_moment_comes_off_the_kind() -> None:
    assert clock.stamp(a_call().due_at) == "2025-07-11 09:15"
    assert clock.stamp(a_call(kind=DEAD_BIRD).due_at) == "2025-07-09 09:15"


def test_a_call_is_open_until_it_is_closed() -> None:
    assert a_call().open
    closed = a_call(closed_at=clock.moment("2025-07-09 16:00"), outcome="basins treated")
    assert not closed.open


def test_a_closed_call_needs_an_outcome() -> None:
    with pytest.raises(UsageError, match="outcome"):
        a_call(closed_at=clock.moment("2025-07-09 16:00"))


def test_nothing_happens_before_the_call_came_in() -> None:
    with pytest.raises(UsageError):
        a_call(visited_at=clock.moment("2025-07-07 09:00"))
    with pytest.raises(UsageError):
        a_call(closed_at=clock.moment("2025-07-07 09:00"), outcome="x")


def test_the_time_taken_is_measured_to_the_visit() -> None:
    made = a_call(visited_at=clock.moment("2025-07-09 09:15"))
    assert made.answered_in() == Decimal("24")
    assert a_call().answered_in() is None


def test_an_unvisited_call_goes_late_when_the_clock_runs_out() -> None:
    made = a_call()
    assert not made.late(clock.moment("2025-07-10 09:00"))
    assert made.late(clock.moment("2025-07-12 09:00"))


def test_a_call_visited_late_stays_late() -> None:
    made = a_call(visited_at=clock.moment("2025-07-14 09:00"))
    assert made.late(clock.moment("2025-07-30 09:00"))
    assert made.late(made.visited_at)  # type: ignore[arg-type]


def test_a_call_visited_in_time_never_goes_late() -> None:
    made = a_call(visited_at=clock.moment("2025-07-09 09:00"))
    assert not made.late(clock.moment("2025-08-01 09:00"))


def test_the_hours_left_go_negative(  # which is how a report sorts them
) -> None:
    made = a_call()
    assert made.hours_left(clock.moment("2025-07-10 09:15")) == Decimal("24")
    assert made.hours_left(clock.moment("2025-07-12 09:15")) == Decimal("-24")


def test_the_references_have_to_be_the_right_kind_of_id() -> None:
    with pytest.raises(UsageError):
        a_call(assigned_to="SI-0001")
    with pytest.raises(UsageError):
        a_call(site="AP-001")
    assert a_call(site="SI-0004", assigned_to="AP-001").site == "SI-0004"


def test_the_line_says_where_the_call_stands() -> None:
    assert "open" in a_call().line()
    assert "visited" in a_call(visited_at=clock.moment("2025-07-09 09:00")).line()
    closed = a_call(
        visited_at=clock.moment("2025-07-09 09:00"),
        closed_at=clock.moment("2025-07-09 16:00"),
        outcome="ditch treated",
    )
    assert "closed" in closed.line()


def test_the_row_stores_utc_and_leaves_the_gaps_empty() -> None:
    row = a_call().to_row()
    assert str(row["taken_at"]).endswith("+00:00")
    assert row["visited_at"] is None
    assert row["site"] is None


def test_a_standing_water_call_sits_between_the_two() -> None:
    assert answer_hours(DEAD_BIRD) < answer_hours(WATER) < answer_hours(BITING)
