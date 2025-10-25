from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def night(crewed: Run) -> Run:
    crewed("product", "stock", "--on", "2025-01-15")
    crewed(
        "block",
        "add",
        "Ardmore east grid",
        "north",
        "--acres",
        "640",
        "--road-miles",
        "18.4",
        "--on",
        "2025-04-01",
    )
    crewed(
        "block",
        "add",
        "Weir street grid",
        "south",
        "--acres",
        "320",
        "--on",
        "2025-04-01",
    )
    crewed("lot", "receive", "Kestrel ULV", "25K-0114", "30 gal", "--on", "2025-04-01")
    return crewed


def test_the_limits_are_printed(night: Run) -> None:
    result = night("spray", "limits")
    assert "1 to 10 miles an hour" in result.output
    assert "48 hours" in result.output


def test_a_clear_night_is_clear(night: Run) -> None:
    result = night(
        "spray",
        "window",
        "Ardmore east grid",
        "--at",
        "2025-07-10 21:10",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    assert "yes" in result.output


def test_a_still_night_is_held(night: Run) -> None:
    result = night(
        "spray",
        "window",
        "Ardmore east grid",
        "--at",
        "2025-07-10 21:10",
        "--wind",
        "0.2",
        "--temperature",
        "74",
    )
    assert "spray.wind" in result.output
    assert "inversion" in result.output


def test_the_afternoon_is_outside_the_window(night: Run) -> None:
    result = night(
        "spray",
        "window",
        "Ardmore east grid",
        "--at",
        "2025-07-10 15:10",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    assert "spray.hours" in result.output


def test_an_apiary_holds_the_block_until_it_is_told(night: Run) -> None:
    night(
        "register",
        "add",
        "Ferrand apiary",
        "north",
        "--kind",
        "apiary",
        "--contact",
        "M. Ferrand",
        "--on",
        "2025-04-01",
    )
    night("block", "link", "Ardmore east grid", "EX-0001")
    held = night(
        "spray",
        "window",
        "Ardmore east grid",
        "--at",
        "2025-07-10 21:10",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    assert "spray.notice" in held.output
    night(
        "spray",
        "tell",
        "EX-0001",
        "Ardmore east grid",
        "--at",
        "2025-07-08 09:00",
        "--from",
        "2025-07-10 20:00",
        "--to",
        "2025-07-11 02:00",
    )
    clear = night(
        "spray",
        "window",
        "Ardmore east grid",
        "--at",
        "2025-07-10 21:10",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    assert "yes" in clear.output


def test_who_is_still_waiting_is_listed_with_the_deadline(night: Run) -> None:
    night(
        "register",
        "add",
        "Ferrand apiary",
        "north",
        "--kind",
        "apiary",
        "--contact",
        "M. Ferrand",
        "--phone",
        "555 0142",
        "--on",
        "2025-04-01",
    )
    night("block", "link", "Ardmore east grid", "EX-0001")
    result = night("spray", "waiting", "Ardmore east grid", "--at", "2025-07-10 21:10")
    assert "2025-07-08 21:10" in result.output
    assert "555 0142" in result.output


def test_a_hatchery_takes_the_block_off_the_board(night: Run) -> None:
    night(
        "register",
        "add",
        "Prewitt trout",
        "north",
        "--kind",
        "aquaculture",
        "--contact",
        "J. Prewitt",
        "--on",
        "2025-04-01",
    )
    night("block", "link", "Ardmore east grid", "EX-0001")
    result = night(
        "spray",
        "board",
        "--at",
        "2025-07-10 21:10",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    assert "spray.absolute" in result.output
    assert "2 rows" in result.output


def test_a_run_is_recorded_and_drawn_off_the_lot(night: Run) -> None:
    result = night(
        "spray",
        "go",
        "Ardmore east grid",
        "LT-0001",
        "--by",
        "AP-001",
        "--start",
        "2025-07-10 21:10",
        "--finish",
        "2025-07-10 22:40",
        "--amount",
        "1.4 gal",
        "--wind",
        "4.5",
        "--temperature",
        "74",
        "--wind-from",
        "SW",
    )
    assert "RN-250710-01" in result.output
    left = night("lot", "show", "LT-0001")
    assert "28.6 gal" in left.output


def test_a_run_on_a_still_night_is_refused(night: Run) -> None:
    result = night(
        "spray",
        "go",
        "Ardmore east grid",
        "LT-0001",
        "--by",
        "AP-001",
        "--start",
        "2025-07-10 21:10",
        "--finish",
        "2025-07-10 22:40",
        "--amount",
        "1.4 gal",
        "--wind",
        "0.2",
        "--temperature",
        "74",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_technician_cannot_make_the_restricted_run(night: Run) -> None:
    result = night(
        "spray",
        "go",
        "Ardmore east grid",
        "LT-0001",
        "--by",
        "AP-002",
        "--start",
        "2025-07-10 21:10",
        "--finish",
        "2025-07-10 22:40",
        "--amount",
        "1.4 gal",
        "--wind",
        "4.5",
        "--temperature",
        "74",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_runs_over_a_window_are_listed(night: Run) -> None:
    night(
        "spray",
        "go",
        "Ardmore east grid",
        "LT-0001",
        "--by",
        "AP-001",
        "--start",
        "2025-07-10 21:10",
        "--finish",
        "2025-07-10 22:40",
        "--amount",
        "1.4 gal",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    result = night("spray", "runs", "--from", "2025-07-01", "--to", "2025-07-31")
    assert "1 row" in result.output
    assert "Kestrel ULV" in result.output


def test_a_run_is_shown_with_the_notices_over_the_block(night: Run) -> None:
    night(
        "register",
        "add",
        "Ferrand apiary",
        "north",
        "--kind",
        "apiary",
        "--contact",
        "M. Ferrand",
        "--on",
        "2025-04-01",
    )
    night("block", "link", "Ardmore east grid", "EX-0001")
    night(
        "spray",
        "tell",
        "EX-0001",
        "Ardmore east grid",
        "--at",
        "2025-07-08 09:00",
        "--from",
        "2025-07-10 20:00",
        "--to",
        "2025-07-11 02:00",
    )
    night(
        "spray",
        "go",
        "Ardmore east grid",
        "LT-0001",
        "--by",
        "AP-001",
        "--start",
        "2025-07-10 21:10",
        "--finish",
        "2025-07-10 22:40",
        "--amount",
        "1.4 gal",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    result = night("spray", "show", "RN-250710-01")
    assert "PA-44192" in result.output
    assert "NT-0001" in result.output
    assert "90.0" in result.output


def test_the_nights_the_truck_went_out_are_listed(night: Run) -> None:
    night(
        "spray",
        "go",
        "Ardmore east grid",
        "LT-0001",
        "--by",
        "AP-001",
        "--start",
        "2025-07-10 21:10",
        "--finish",
        "2025-07-10 22:40",
        "--amount",
        "1.4 gal",
        "--wind",
        "4.5",
        "--temperature",
        "74",
    )
    result = night("spray", "nights", "--from", "2025-07-01", "--to", "2025-07-31")
    assert "2025-07-10" in result.output
    assert "640" in result.output


def test_the_season_counts_the_passes_over_a_block(night: Run) -> None:
    for day in ("10", "17"):
        night(
            "spray",
            "go",
            "Ardmore east grid",
            "LT-0001",
            "--by",
            "AP-001",
            "--start",
            f"2025-07-{day} 21:10",
            "--finish",
            f"2025-07-{day} 22:40",
            "--amount",
            "1.4 gal",
            "--wind",
            "4.5",
            "--temperature",
            "74",
        )
    result = night("spray", "season", "Ardmore east grid", "2025")
    assert "2.00" in result.output
