from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def sent(started: Run) -> Run:
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
        "60",
    )
    return started


def test_a_pool_reports_how_much_of_the_jar_is_gone(sent: Run) -> None:
    result = sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    assert "PL-250605-01" in result.output
    assert "50 of 120 pooled" in result.output


def test_the_jar_runs_out(sent: Run) -> None:
    for _ in range(2):
        sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    result = sent(
        "pool",
        "submit",
        "CO-250604-01",
        "CXPP",
        "50",
        "--on",
        "2025-06-05",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_pool_over_fifty_is_refused(sent: Run) -> None:
    result = sent(
        "pool",
        "submit",
        "CO-250604-01",
        "CXPP",
        "60",
        "--on",
        "2025-06-05",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_result_is_recorded(sent: Run) -> None:
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    result = sent(
        "pool",
        "result",
        "PL-250605-01",
        "West Nile",
        "positive",
        "--on",
        "2025-06-09",
        "--ct",
        "27.4",
    )
    assert "positive" in result.output


def test_a_cycle_threshold_on_a_negative_is_refused(sent: Run) -> None:
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    result = sent(
        "pool",
        "result",
        "PL-250605-01",
        "West Nile",
        "negative",
        "--on",
        "2025-06-09",
        "--ct",
        "27.4",
        expect=1,
    )
    assert result.exit_code != 0


def test_an_unknown_outcome_is_refused_by_the_option(sent: Run) -> None:
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    result = sent("pool", "result", "PL-250605-01", "West Nile", "maybe", expect=2)
    assert result.exit_code != 0


def test_a_pool_is_shown_with_every_virus(sent: Run) -> None:
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    sent("pool", "result", "PL-250605-01", "West Nile", "positive", "--on", "2025-06-09")
    result = sent("pool", "show", "PL-250605-01")
    assert "Culex pipiens" in result.output
    assert "2025-W23" in result.output
    assert "positive" in result.output
    assert "pending" in result.output


def test_what_is_still_out_is_listed(sent: Run) -> None:
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    sent("pool", "result", "PL-250605-01", "West Nile", "negative", "--on", "2025-06-09")
    result = sent("pool", "waiting")
    assert "PL-250605-02" in result.output
    assert "1 row" in result.output


def test_the_week_says_which_pools_count_for_the_virus(sent: Run) -> None:
    sent("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    sent("pool", "submit", "CO-250604-01", "AEVX", "50", "--on", "2025-06-05")
    sent("pool", "result", "PL-250605-01", "West Nile", "positive", "--on", "2025-06-09")
    sent("pool", "result", "PL-250605-02", "West Nile", "negative", "--on", "2025-06-09")
    result = sent("pool", "week", "2025-W23")
    assert "2 rows" in result.output
    assert "yes" in result.output
    assert "no" in result.output


def test_the_limits_are_printed(sent: Run) -> None:
    result = sent("pool", "limits")
    assert "50" in result.output
    assert "West Nile" in result.output
