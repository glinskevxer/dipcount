from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def lab(crewed: Run) -> Run:
    crewed("product", "stock", "--on", "2025-01-15")
    crewed(
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
    return crewed


def bottles(*counts: int) -> list[str]:
    args: list[str] = []
    for number, knocked in enumerate(counts, start=1):
        args += ["--bottle", str(number), str(knocked), "25"]
    return args


def test_the_control_bands_are_printed(lab: Run) -> None:
    result = lab("assay", "controls")
    assert "the run says nothing" in result.output


def test_a_flat_assay_reads_susceptible(lab: Run) -> None:
    result = lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(25, 25, 25, 25),
    )
    assert "BA-250812-01" in result.output
    assert "susceptible" in result.output


def test_survivors_read_resistant(lab: Run) -> None:
    result = lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(20, 20, 20, 20),
    )
    assert "resistant" in result.output


def test_a_control_inside_the_band_says_it_was_corrected(lab: Run) -> None:
    result = lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(23, 23, 23, 23),
        "--bottle",
        "control",
        "2",
        "25",
    )
    assert "corrected for what died" in result.output


def test_a_control_over_the_ceiling_voids_the_run(lab: Run) -> None:
    result = lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(23, 23, 23, 23),
        "--bottle",
        "control",
        "6",
        "25",
    )
    assert "void" in result.output


def test_more_readings_are_added_afterwards(lab: Run) -> None:
    lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(23, 23, 23, 23),
    )
    result = lab("assay", "read", "BA-250812-01", "control", "2", "25", "--minute", "30")
    assert "possible resistance" in result.output or "resistant" in result.output


def test_an_assay_is_shown_with_its_bottles(lab: Run) -> None:
    lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(25, 25, 25, 25),
    )
    result = lab("assay", "show", "BA-250812-01")
    assert "diagnostic time" in result.output
    assert "4 rows" in result.output


def test_the_board_names_the_mode_of_action(lab: Run) -> None:
    lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(20, 20, 20, 20),
    )
    result = lab("assay", "board", "--on", "2025-08-20")
    assert "growth regulator" in result.output
    assert "yes" in result.output


def test_the_advice_for_a_site_names_the_products_in_doubt(lab: Run) -> None:
    lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(20, 20, 20, 20),
    )
    result = lab("assay", "advice", "SI-0001", "--on", "2025-08-20")
    assert "Hesper 30 briquets" in result.output
    assert "resistance.species" in result.output


def test_the_advice_leaves_the_other_actives_alone(lab: Run) -> None:
    lab(
        "assay",
        "run",
        "S-methoprene",
        "CXPP",
        "--dose",
        "43",
        "--minutes",
        "30",
        "--on",
        "2025-08-12",
        "--zone",
        "north",
        *bottles(20, 20, 20, 20),
    )
    result = lab("assay", "advice", "SI-0001", "--on", "2025-08-20")
    lines = [line for line in result.output.splitlines() if "Bactilore WSP" in line]
    assert lines
    assert "resistance.species" not in lines[0]


def test_what_has_never_been_run_is_listed(lab: Run) -> None:
    result = lab("assay", "untested", "SI-0001", "--on", "2025-08-20")
    assert "CXPP" in result.output
    assert "S-methoprene" in result.output
