from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def desk(started: Run) -> Run:
    started(
        "site",
        "add",
        "north",
        "Weller Road",
        "--habitat",
        "catch_basin",
        "--extent",
        "14 each",
        "--on",
        "2025-03-01",
    )
    return started


def busy(run: Run) -> None:
    run("trap", "add", "Ambrose gravid 1", "north", "--kind", "gravid", "--on", "2025-04-01")
    run(
        "trap",
        "collect",
        "TR-0001",
        "--set",
        "2025-07-06 16:30",
        "--pulled",
        "2025-07-07 08:15",
        "--catch",
        "CXPP",
        "F",
        "400",
    )
    for _ in range(4):
        run("pool", "submit", "CO-250707-01", "CXPP", "50", "--on", "2025-07-08")
    for number in range(1, 5):
        run(
            "pool",
            "result",
            f"PL-250708-{number:02d}",
            "West Nile",
            "positive",
            "--on",
            "2025-07-09",
        )


def test_the_kinds_and_their_clocks_are_printed(desk: Run) -> None:
    result = desk("call", "kinds")
    assert "dead bird" in result.output
    assert "decays" in result.output


def test_a_call_reports_when_it_is_due(desk: Run) -> None:
    result = desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "biting",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
        "--caller",
        "A. Sandoval",
    )
    assert "SR-0001" in result.output
    assert "2025-07-11 09:15" in result.output


def test_a_busy_week_says_the_clock_was_cut(desk: Run) -> None:
    busy(desk)
    result = desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "dead bird",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    assert "clock cut from 24 hours" in result.output


def test_a_quiet_zone_keeps_the_full_clock(desk: Run) -> None:
    busy(desk)
    result = desk(
        "call",
        "take",
        "12 Rowe Lane",
        "--kind",
        "dead bird",
        "--zone",
        "south",
        "--at",
        "2025-07-08 09:15",
    )
    assert "clock cut" not in result.output


def test_a_call_is_assigned_answered_and_closed(desk: Run) -> None:
    desk(
        "crew",
        "add",
        "K. Brennaman",
        "PA-44192",
        "--grade",
        "certified",
        "--category",
        "core",
        "--category",
        "public health",
        "--certified",
        "2024-03-01",
        "--expires",
        "2027-03-01",
    )
    desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "biting",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    desk("call", "assign", "SR-0001", "AP-001")
    answered = desk("call", "answer", "SR-0001", "--at", "2025-07-09 09:15", "--site", "SI-0001")
    assert "in time" in answered.output
    closed = desk("call", "close", "SR-0001", "basins treated", "--at", "2025-07-09 16:00")
    assert "basins treated" in closed.output


def test_a_late_answer_says_so(desk: Run) -> None:
    desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "dead bird",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    result = desk("call", "answer", "SR-0001", "--at", "2025-07-11 09:15")
    assert "late" in result.output


def test_the_waiting_list_puts_the_tightest_clock_first(desk: Run) -> None:
    desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "biting",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    desk(
        "call",
        "take",
        "12 Rowe Lane",
        "--kind",
        "dead bird",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    result = desk("call", "waiting", "--at", "2025-07-08 12:00")
    lines = [line for line in result.output.splitlines() if line.startswith("SR-")]
    assert lines[0].startswith("SR-0002")


def test_only_the_late_ones_can_be_asked_for(desk: Run) -> None:
    desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "dead bird",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    desk(
        "call",
        "take",
        "12 Rowe Lane",
        "--kind",
        "biting",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    result = desk("call", "waiting", "--at", "2025-07-09 12:00", "--late")
    assert "1 row" in result.output
    assert "SR-0001" in result.output


def test_a_call_is_shown_with_its_level(desk: Run) -> None:
    busy(desk)
    desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "dead bird",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    result = desk("call", "show", "SR-0001", "--at", "2025-07-08 12:00")
    assert "response level" in result.output
    assert "hours allowed" in result.output
    assert "12" in result.output


def test_the_season_counts_what_was_answered_in_time(desk: Run) -> None:
    desk(
        "call",
        "take",
        "1400 Weir Street",
        "--kind",
        "biting",
        "--zone",
        "north",
        "--at",
        "2025-07-08 09:15",
    )
    desk("call", "answer", "SR-0001", "--at", "2025-07-09 09:15")
    result = desk("call", "season", "--from", "2025-07-01", "--to", "2025-07-31")
    assert "100%" in result.output
    assert "biting" in result.output
