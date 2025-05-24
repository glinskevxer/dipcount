from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def tested(started: Run) -> Run:
    started("trap", "add", "Ambrose gravid 1", "north", "--kind", "gravid", "--on", "2025-04-01")
    started(
        "trap",
        "collect",
        "TR-0001",
        "--set",
        "2025-06-03 16:30",
        "--pulled",
        "2025-06-04 08:15",
        "--catch",
        "CXPP",
        "F",
        "120",
        "--catch",
        "AEVX",
        "F",
        "300",
    )
    started("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    started("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    started("pool", "result", "PL-250605-01", "West Nile", "positive", "--on", "2025-06-09")
    started("pool", "result", "PL-250605-02", "West Nile", "negative", "--on", "2025-06-09")
    return started


def test_the_ladder_is_printed(tested: Run) -> None:
    result = tested("virus", "ladder")
    assert "emergency" in result.output
    assert "1.5" in result.output


def test_the_viruses_and_their_vectors_are_listed(tested: Run) -> None:
    result = tested("virus", "viruses")
    assert "West Nile" in result.output
    assert "CXPP" in result.output


def test_a_week_reports_both_halves_and_the_level(tested: Run) -> None:
    result = tested("virus", "week", "2025-W23")
    assert "abundance" in result.output
    assert "120.00 per night" in result.output
    assert "vector index" in result.output
    assert "estimated rate" in result.output


def test_the_abundance_leaves_out_what_does_not_carry(tested: Run) -> None:
    result = tested("virus", "week", "2025-W23")
    assert "120.00 per night" in result.output
    assert "420" not in result.output


def test_the_reasons_are_printed_under_the_figures(tested: Run) -> None:
    result = tested("virus", "week", "2025-W23")
    assert "species that carry it" in result.output


def test_a_week_with_nothing_in_it(tested: Run) -> None:
    result = tested("virus", "week", "2025-W30")
    assert "none" in result.output


def test_a_season_runs_a_week_at_a_time(tested: Run) -> None:
    result = tested("virus", "season", "2025", "--first", "22", "--last", "25")
    assert "4 rows" in result.output
    assert "2025-W23" in result.output


def test_the_first_positive_week_is_reported(tested: Run) -> None:
    result = tested("virus", "first", "2025")
    assert "2025-W23" in result.output


def test_a_season_with_nothing_positive_says_so(tested: Run) -> None:
    result = tested("virus", "first", "2025", "--virus", "La Crosse")
    assert "nothing positive" in result.output


def test_the_peak_week_is_reported(tested: Run) -> None:
    result = tested("virus", "peak", "2025", "--first", "22", "--last", "25")
    assert "2025-W23" in result.output


def test_a_season_with_no_index_says_so(tested: Run) -> None:
    result = tested("virus", "peak", "2025", "--virus", "La Crosse")
    assert "no vector index" in result.output
