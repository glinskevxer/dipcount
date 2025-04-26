from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def trapped(started: Run) -> Run:
    started("trap", "add", "Ambrose gravid 1", "north", "--kind", "gravid", "--on", "2024-04-01")
    started("trap", "add", "Kettle light 1", "north", "--kind", "light", "--on", "2024-04-01")
    return started


def pull(run: Run, trap: str, day: str, *catches: str, broken: bool = False) -> object:
    args = [
        "trap",
        "collect",
        trap,
        "--set",
        f"2025-06-{int(day) - 1:02d} 16:30",
        "--pulled",
        f"2025-06-{int(day):02d} 08:15",
    ]
    for chunk in range(0, len(catches), 3):
        args += ["--catch", *catches[chunk : chunk + 3]]
    if broken:
        args.append("--broken")
    return run(*args)


def test_the_kinds_are_listed_with_their_figures(trapped: Run) -> None:
    result = trapped("trap", "kinds")
    assert "gravid trap over hay infusion" in result.output
    assert "50" in result.output


def test_a_trap_is_added_and_listed(trapped: Run) -> None:
    result = trapped("trap", "list")
    assert "TR-0001" in result.output
    assert "2 rows" in result.output


def test_traps_narrow_by_kind(trapped: Run) -> None:
    result = trapped("trap", "list", "--kind", "gravid")
    assert "1 row" in result.output


def test_a_collection_reports_its_index(trapped: Run) -> None:
    result = pull(trapped, "TR-0001", "4", "CXPP", "F", "42", "CXPP", "M", "130")
    assert "42 females and 130 males" in result.output  # type: ignore[attr-defined]
    assert "42.00/night" in result.output  # type: ignore[attr-defined]


def test_a_trap_that_did_not_run_says_so(trapped: Run) -> None:
    result = pull(trapped, "TR-0001", "4", broken=True)
    assert "did not run" in result.output  # type: ignore[attr-defined]


def test_a_broken_trap_with_a_catch_is_refused(trapped: Run) -> None:
    args = [
        "trap",
        "collect",
        "TR-0001",
        "--set",
        "2025-06-03 16:30",
        "--pulled",
        "2025-06-04 08:15",
        "--broken",
        "--catch",
        "CXPP",
        "F",
        "42",
    ]
    result = trapped(*args, expect=1)
    assert result.exit_code != 0


def test_an_unknown_species_is_refused(trapped: Run) -> None:
    args = [
        "trap",
        "collect",
        "TR-0001",
        "--set",
        "2025-06-03 16:30",
        "--pulled",
        "2025-06-04 08:15",
        "--catch",
        "ZZZZ",
        "F",
        "42",
    ]
    result = trapped(*args, expect=1)
    assert result.exit_code != 0


def test_a_collection_is_shown_with_its_jar(trapped: Run) -> None:
    pull(trapped, "TR-0001", "4", "CXPP", "F", "42", "CXPP", "M", "130")
    result = trapped("trap", "show", "CO-250604-01")
    assert "gravid trap over hay infusion" in result.output
    assert "2025-W23" in result.output
    assert "42.00" in result.output


def test_the_round_names_what_has_not_been_run(trapped: Run) -> None:
    pull(trapped, "TR-0001", "4")
    result = trapped("trap", "due", "--on", "2025-06-08")
    assert "TR-0002" in result.output
    assert "1 row" in result.output
    assert "never" in result.output


def test_the_index_reports_the_week(trapped: Run) -> None:
    pull(trapped, "TR-0001", "4", "CXPP", "F", "40")
    result = trapped("trap", "index", "2025-W23")
    assert "40.00" in result.output
    assert "over figure" in result.output
    assert "yes" in result.output


def test_a_first_season_reports_no_baseline(trapped: Run) -> None:
    pull(trapped, "TR-0001", "4", "CXPP", "F", "40")
    result = trapped("trap", "index", "2025-W23")
    assert "none" in result.output


def test_a_broken_trap_is_dropped_out_of_the_index(trapped: Run) -> None:
    pull(trapped, "TR-0001", "4", "CXPP", "F", "40")
    pull(trapped, "TR-0001", "6", broken=True)
    result = trapped("trap", "index", "2025-W23")
    assert "40.00" in result.output
    assert "dropped" in result.output


def test_the_season_runs_a_week_at_a_time(trapped: Run) -> None:
    result = trapped("trap", "season", "2025", "--first", "22", "--last", "24")
    assert "3 rows" in result.output
    assert "2025-W23" in result.output


def test_a_trap_is_retired(trapped: Run) -> None:
    result = trapped("trap", "retire", "TR-0001", "--on", "2025-09-01", "--why", "fence came down")
    assert "2025-09-01" in result.output
