from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def working(crewed: Run) -> Run:
    crewed("product", "stock", "--on", "2025-01-15")
    crewed(
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
    crewed("trap", "add", "Ambrose gravid 1", "north", "--kind", "gravid", "--on", "2025-03-01")
    crewed("lot", "receive", "Bactilore G", "24G-1187", "400 lb", "--on", "2025-03-01")
    crewed(
        "dip",
        "record",
        "SI-0001",
        "--at",
        "2025-06-04 09:00",
        "--dips",
        "10",
        "--count",
        "CXPP",
        "2",
        "12",
    )
    crewed(
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
        "60",
    )
    crewed("pool", "submit", "CO-250604-01", "CXPP", "50", "--on", "2025-06-05")
    crewed("pool", "result", "PL-250605-01", "West Nile", "positive", "--on", "2025-06-09")
    crewed(
        "treat",
        "apply",
        "SI-0001",
        "LT-0001",
        "--by",
        "AP-001",
        "--at",
        "2025-06-04 10:40",
    )
    return crewed


def test_the_week_report_covers_every_section(working: Run) -> None:
    result = working("report", "week", "2025-W23")
    for heading in ("larval surveillance", "adult surveillance", "work done", "calls"):
        assert heading in result.output


def test_the_week_report_narrows_to_a_zone(working: Run) -> None:
    result = working("report", "week", "2025-W23", "--zone", "south")
    assert "zone ZN-002" in result.output


def test_a_bad_week_label_is_refused(working: Run) -> None:
    result = working("report", "week", "2026-W53", expect=1)
    assert result.exit_code != 0


def test_the_season_report_names_the_first_positive(working: Run) -> None:
    result = working("report", "season", "2025", "--on", "2025-08-01")
    assert "first positive" in result.output
    assert "2025-W23" in result.output


def test_the_board_lists_what_needs_attention(working: Run) -> None:
    result = working("report", "board", "--on", "2025-08-01")
    assert "board" in result.output
    assert "calls" in result.output


def test_the_use_return_prints_the_applications(working: Run) -> None:
    result = working("report", "use", "--year", "2025")
    assert "pesticide use" in result.output
    assert "73049-20" in result.output


def test_the_use_return_comes_out_as_a_file(working: Run) -> None:
    result = working("report", "use", "--year", "2025", "--csv")
    assert result.output.splitlines()[0].startswith("day,record,place")


def test_a_use_return_needs_a_year_or_a_window(working: Run) -> None:
    result = working("report", "use", expect=2)
    assert result.exit_code != 0


def test_a_use_window_is_accepted(working: Run) -> None:
    result = working("report", "use", "--from", "2025-06-01", "--to", "2025-06-30")
    assert "TX-250604-01" in result.output


def test_the_registers_are_listed(working: Run) -> None:
    result = working("report", "registers")
    assert "treatments" in result.output
    assert "sites" in result.output


def test_one_register_is_written_out(working: Run, tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    result = working("report", "export", "sites", "--into", str(tmp_path / "out"))
    assert "sites.csv" in result.output
    assert (tmp_path / "out" / "sites.csv").exists()


def test_every_register_is_written_out(working: Run, tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    result = working("report", "export", "all", "--into", str(tmp_path / "out"))
    assert "12 files" in result.output


def test_an_unknown_register_is_refused(working: Run, tmp_path: object) -> None:
    result = working("report", "export", "nothing", "--into", str(tmp_path), expect=1)
    assert result.exit_code != 0
