from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def listed(started: Run) -> Run:
    started(
        "site",
        "add",
        "north",
        "Weller Road basins",
        "--habitat",
        "catch_basin",
        "--extent",
        "14 each",
        "--on",
        "2025-03-01",
    )
    started(
        "site",
        "add",
        "north",
        "Sawyer marsh",
        "--habitat",
        "cattail_marsh",
        "--extent",
        "6 acre",
        "--on",
        "2025-03-01",
    )
    return started


def test_the_stage_codes_are_explained(listed: Run) -> None:
    result = listed("dip", "stages")
    assert "egg raft" in result.output
    assert "instar 3" in result.output


def test_a_dry_visit_is_recorded(listed: Run) -> None:
    result = listed("dip", "record", "SI-0001", "--at", "2025-06-04 09:15", "--dry")
    assert "IN-250604-01" in result.output
    assert "dry" in result.output


def test_a_visit_with_counts_reaches_a_verdict(listed: Run) -> None:
    result = listed(
        "dip",
        "record",
        "SI-0001",
        "--at",
        "2025-06-04 09:15",
        "--dips",
        "10",
        "--count",
        "CXPP",
        "2",
        "8",
    )
    assert "treat" in result.output
    assert "0.80/dip against 0.25" in result.output
    assert "halved" in result.output


def test_a_dash_stands_for_an_unidentified_sample(listed: Run) -> None:
    result = listed(
        "dip",
        "record",
        "SI-0001",
        "--at",
        "2025-06-04 09:15",
        "--dips",
        "10",
        "--count",
        "-",
        "2",
        "8",
    )
    assert "against 0.50" in result.output


def test_a_bad_stage_is_refused(listed: Run) -> None:
    result = listed(
        "dip",
        "record",
        "SI-0001",
        "--at",
        "2025-06-04 09:15",
        "--dips",
        "10",
        "--count",
        "CXPP",
        "9",
        "8",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_round_lists_what_is_due(listed: Run) -> None:
    result = listed("dip", "due", "--on", "2025-06-04")
    assert "2 rows" in result.output
    assert "SI-0001" in result.output


def test_a_visited_site_leaves_the_round(listed: Run) -> None:
    listed("dip", "record", "SI-0001", "--at", "2025-06-04 09:15", "--dips", "10")
    result = listed("dip", "due", "--on", "2025-06-05")
    assert "1 row" in result.output
    assert "SI-0002" in result.output


def test_the_round_narrows_to_a_zone(listed: Run) -> None:
    listed(
        "site",
        "add",
        "south",
        "Dunlap basins",
        "--habitat",
        "catch_basin",
        "--extent",
        "9 each",
        "--on",
        "2025-03-01",
    )
    result = listed("dip", "due", "--on", "2025-06-04", "--zone", "south")
    assert "1 row" in result.output
    assert "SI-0003" in result.output


def test_an_inspection_is_shown_with_its_tallies(listed: Run) -> None:
    listed(
        "dip",
        "record",
        "SI-0001",
        "--at",
        "2025-06-04 09:15",
        "--dips",
        "10",
        "--count",
        "CXPP",
        "2",
        "8",
        "--count",
        "CXPP",
        "P",
        "2",
    )
    result = listed("dip", "show", "IN-250604-01")
    assert "pupa" in result.output
    assert "instar 2" in result.output
    assert "2025-W23" in result.output


def test_a_site_history_is_listed(listed: Run) -> None:
    listed("dip", "record", "SI-0001", "--at", "2025-06-04 09:15", "--dips", "10")
    listed("dip", "record", "SI-0001", "--at", "2025-06-26 09:15", "--dry")
    result = listed("dip", "site", "SI-0001")
    assert "2 rows" in result.output
    assert "dry" in result.output


def test_a_history_is_cut_at_a_day(listed: Run) -> None:
    listed("dip", "record", "SI-0001", "--at", "2025-06-04 09:15", "--dips", "10")
    listed("dip", "record", "SI-0001", "--at", "2025-06-26 09:15", "--dry")
    result = listed("dip", "site", "SI-0001", "--since", "2025-06-10")
    assert "1 row" in result.output


def test_a_week_gathers_the_visits(listed: Run) -> None:
    listed("dip", "record", "SI-0001", "--at", "2025-06-04 09:15", "--dips", "10")
    listed("dip", "record", "SI-0002", "--at", "2025-06-05 09:15", "--dips", "10")
    result = listed("dip", "week", "2025-W23")
    assert "2 rows" in result.output
    assert "2025-06-01 to 2025-06-07" in result.output


def test_a_week_outside_the_year_is_refused(listed: Run) -> None:
    result = listed("dip", "week", "2026-W53", expect=1)
    assert result.exit_code != 0
