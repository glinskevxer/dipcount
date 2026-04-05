from __future__ import annotations

import datetime as dt

import pytest

from dipcount import clock
from dipcount.errors import NotFound, UsageError
from dipcount.model.audit import Entry
from dipcount.store import Book, upgrade
from dipcount.store import audit as trail


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    return book


def test_a_line_comes_back_with_a_sequence(district: Book) -> None:
    entry = trail.record(district, "R. Vandeburg", "listed", "SI-0001", "14 basins")
    assert entry.seq == 1
    assert entry.actor == "R. Vandeburg"
    assert entry.detail == "14 basins"


def test_the_sequence_numbers_run_upwards(district: Book) -> None:
    first = trail.record(district, "R. Vandeburg", "listed", "SI-0001")
    second = trail.record(district, "R. Vandeburg", "listed", "SI-0002")
    assert second.seq > first.seq


def test_a_line_needs_a_name_and_an_action() -> None:
    when = clock.now()
    with pytest.raises(UsageError):
        Entry(1, when, "  ", "listed", "SI-0001")
    with pytest.raises(UsageError):
        Entry(1, when, "R. Vandeburg", " ", "SI-0001")


def test_a_line_needs_a_moment_with_a_zone() -> None:
    with pytest.raises(UsageError):
        Entry(1, dt.datetime(2025, 6, 1, 9, 0), "R. Vandeburg", "listed", "SI-0001")  # noqa: DTZ001


def test_the_moment_is_stored_in_utc_and_read_back_local(district: Book) -> None:
    at = clock.moment("2025-06-04 21:30")
    entry = trail.record(district, "R. Vandeburg", "listed", "SI-0001", at=at)
    stored = district.value("SELECT at FROM audit WHERE seq = ?", (entry.seq,))
    assert str(stored).endswith("+00:00")
    assert clock.stamp(entry.at) == "2025-06-04 21:30"


def test_a_line_prints_the_way_a_report_wants_it(district: Book) -> None:
    at = clock.moment("2025-06-04 21:30")
    entry = trail.record(district, "R. Vandeburg", "retired", "SI-0001", "basins rebuilt", at=at)
    assert entry.line() == "2025-06-04 21:30  R. Vandeburg  retired SI-0001  basins rebuilt"


def test_a_line_with_no_detail_prints_without_trailing_space(district: Book) -> None:
    at = clock.moment("2025-06-04 21:30")
    entry = trail.record(district, "R. Vandeburg", "listed", "SI-0001", at=at)
    assert entry.line().endswith("listed SI-0001")


def test_lines_are_found_by_subject(district: Book) -> None:
    trail.record(district, "A", "listed", "SI-0001")
    trail.record(district, "B", "remeasured", "SI-0001")
    trail.record(district, "A", "listed", "SI-0002")
    about = trail.about(district, "SI-0001")
    assert [entry.action for entry in about] == ["listed", "remeasured"]


def test_lines_are_found_by_actor(district: Book) -> None:
    trail.record(district, "A", "listed", "SI-0001")
    trail.record(district, "B", "listed", "SI-0002")
    assert [entry.subject for entry in trail.by_actor(district, "B")] == ["SI-0002"]


def test_a_window_takes_the_lines_inside_it(district: Book) -> None:
    early = clock.moment("2025-06-04 08:00")
    late = clock.moment("2025-06-05 08:00")
    trail.record(district, "A", "listed", "SI-0001", at=early)
    trail.record(district, "A", "listed", "SI-0002", at=late)
    found = trail.between(district, early, late)
    assert [entry.subject for entry in found] == ["SI-0001"]


def test_a_local_day_holds_what_happened_that_day(district: Book) -> None:
    trail.record(district, "A", "listed", "SI-0001", at=clock.moment("2025-06-04 23:30"))
    trail.record(district, "A", "listed", "SI-0002", at=clock.moment("2025-06-05 00:30"))
    fourth = trail.on_day(district, dt.date(2025, 6, 4))
    assert [entry.subject for entry in fourth] == ["SI-0001"]


def test_the_walk_can_be_cut_to_the_last_few(district: Book) -> None:
    for number in range(1, 6):
        trail.record(district, "A", "listed", f"SI-{number:04d}")
    assert [entry.subject for entry in trail.walk(district, limit=2)] == ["SI-0004", "SI-0005"]
    assert len(trail.walk(district)) == 5


def test_the_distinct_actions_come_back_sorted(district: Book) -> None:
    trail.record(district, "A", "retired", "SI-0001")
    trail.record(district, "A", "listed", "SI-0002")
    trail.record(district, "A", "listed", "SI-0003")
    assert trail.actions(district) == ["listed", "retired"]


def test_a_line_that_is_not_there(district: Book) -> None:
    with pytest.raises(NotFound):
        trail.get(district, 99)
