from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def gridded(started: Run) -> Run:
    started(
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
    started(
        "block",
        "add",
        "Weir street grid",
        "south",
        "--acres",
        "320",
        "--on",
        "2025-04-01",
    )
    started(
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
    return started


def test_a_block_is_added_and_listed(gridded: Run) -> None:
    result = gridded("block", "list")
    assert "BK-0001" in result.output
    assert "640" in result.output
    assert "2 rows" in result.output


def test_a_block_name_is_not_reused(gridded: Run) -> None:
    result = gridded(
        "block",
        "add",
        "Ardmore east grid",
        "south",
        "--acres",
        "100",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_register_is_listed_with_its_notice_period(gridded: Run) -> None:
    result = gridded("register", "list")
    assert "EX-0001" in result.output
    assert "48 h" in result.output


def test_an_absolute_entry_says_never(gridded: Run) -> None:
    gridded(
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
    result = gridded("register", "list", "--kind", "aquaculture")
    assert "never" in result.output


def test_an_aquaculture_entry_needs_a_contact(gridded: Run) -> None:
    result = gridded(
        "register",
        "add",
        "Prewitt trout",
        "north",
        "--kind",
        "aquaculture",
        "--on",
        "2025-04-01",
        expect=1,
    )
    assert result.exit_code != 0


def test_an_entry_is_put_inside_a_block(gridded: Run) -> None:
    result = gridded("block", "link", "Ardmore east grid", "EX-0001")
    assert "inside" in result.output
    shown = gridded("block", "show", "Ardmore east grid", "--on", "2025-07-10")
    assert "Ferrand apiary" in shown.output


def test_the_register_column_counts_what_is_inside(gridded: Run) -> None:
    gridded("block", "link", "Ardmore east grid", "EX-0001")
    result = gridded("block", "list", "--on", "2025-07-10")
    assert "1" in result.output


def test_the_register_listing_says_which_blocks(gridded: Run) -> None:
    gridded("block", "link", "Ardmore east grid", "EX-0001")
    result = gridded("register", "list")
    assert "BK-0001" in result.output


def test_an_entry_is_taken_back_out(gridded: Run) -> None:
    gridded("block", "link", "Ardmore east grid", "EX-0001")
    result = gridded("block", "unlink", "Ardmore east grid", "EX-0001")
    assert "taken out" in result.output
    again = gridded("block", "unlink", "Ardmore east grid", "EX-0001", expect=1)
    assert again.exit_code != 0


def test_an_entry_comes_off_the_register(gridded: Run) -> None:
    result = gridded("register", "remove", "EX-0001", "--on", "2025-06-01", "--why", "hives moved")
    assert "2025-06-01" in result.output
    later = gridded("register", "list", "--on", "2025-07-10")
    assert "0 rows" in later.output


def test_a_block_is_retired(gridded: Run) -> None:
    result = gridded("block", "retire", "Ardmore east grid", "--on", "2025-09-01")
    assert "2025-09-01" in result.output
    later = gridded("block", "list", "--on", "2025-09-02")
    assert "1 row" in later.output


def test_an_entry_asking_for_more_notice_than_usual(gridded: Run) -> None:
    gridded(
        "register",
        "add",
        "Kellams bees",
        "north",
        "--kind",
        "apiary",
        "--contact",
        "P. Kellams",
        "--notice",
        "72",
        "--on",
        "2025-04-01",
    )
    result = gridded("register", "list", "--kind", "apiary")
    assert "72 h" in result.output
