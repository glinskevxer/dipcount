from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def shopped(started: Run) -> Run:
    started(
        "shop",
        "add",
        "40-11872",
        "--kind",
        "ulv fogger",
        "--maker",
        "Larkspur",
        "--model",
        "XLR-40",
        "--nominal",
        "1.5 fl oz",
        "--swath",
        "300",
        "--on",
        "2024-05-01",
    )
    started(
        "shop",
        "add",
        "G6-2201",
        "--kind",
        "granule spreader",
        "--maker",
        "Hallam",
        "--model",
        "G-6",
        "--nominal",
        "40 lb",
        "--swath",
        "30",
        "--on",
        "2024-05-01",
    )
    return started


def test_the_machines_are_listed(shopped: Run) -> None:
    result = shopped("shop", "list", "--on", "2025-06-12")
    assert "EQ-001" in result.output
    assert "never" in result.output
    assert "2 rows" in result.output


def test_a_serial_number_is_used_once(shopped: Run) -> None:
    result = shopped(
        "shop",
        "add",
        "40-11872",
        "--kind",
        "ulv fogger",
        "--maker",
        "Larkspur",
        "--model",
        "XLR-40",
        expect=1,
    )
    assert result.exit_code != 0


def test_a_calibration_reports_the_rate_and_the_due_day(shopped: Run) -> None:
    result = shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.5 fl oz",
        "--droplet",
        "17",
        "--speed",
        "10",
    )
    assert "CA-250612-01" in result.output
    assert "due 2025-07-12" in result.output
    assert "rate" in result.output


def test_a_calibration_without_a_speed_says_so(shopped: Run) -> None:
    result = shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.5 fl oz",
        "--droplet",
        "17",
    )
    assert "no rate" in result.output


def test_a_coarse_droplet_is_reported_under_the_calibration(shopped: Run) -> None:
    result = shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.5 fl oz",
        "--droplet",
        "42",
        "--speed",
        "10",
    )
    assert "equipment.droplet" in result.output


def test_a_drifted_flow_is_reported_too(shopped: Run) -> None:
    result = shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.9 fl oz",
        "--droplet",
        "17",
        "--speed",
        "10",
    )
    assert "equipment.flow" in result.output


def test_a_machine_becomes_usable_after_a_good_check(shopped: Run) -> None:
    shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.5 fl oz",
        "--droplet",
        "17",
        "--speed",
        "10",
    )
    result = shopped("shop", "list", "--on", "2025-06-12")
    assert "yes" in result.output


def test_a_machine_shows_its_history(shopped: Run) -> None:
    shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.5 fl oz",
        "--droplet",
        "17",
        "--speed",
        "10",
    )
    result = shopped("shop", "show", "EQ-001", "--on", "2025-06-12")
    assert "CA-250612-01" in result.output
    assert "usable" in result.output


def test_what_is_due_is_listed(shopped: Run) -> None:
    shopped(
        "shop",
        "calibrate",
        "EQ-001",
        "--on",
        "2025-06-12",
        "--flow",
        "1.5 fl oz",
        "--droplet",
        "17",
        "--speed",
        "10",
    )
    result = shopped("shop", "due", "--on", "2025-07-20")
    assert "2 rows" in result.output
    assert "8" in result.output


def test_the_driving_speed_comes_off_the_last_flow(shopped: Run) -> None:
    shopped(
        "shop",
        "calibrate",
        "EQ-002",
        "--on",
        "2025-06-12",
        "--flow",
        "40 lb",
        "--speed",
        "6",
    )
    result = shopped("shop", "speed", "EQ-002", "6.25 lb", "--on", "2025-06-12")
    assert "drive at" in result.output


def test_a_machine_never_calibrated_gives_no_speed(shopped: Run) -> None:
    result = shopped("shop", "speed", "EQ-001", "0.01 fl oz", "--on", "2025-06-12")
    assert "no calibration" in result.output


def test_a_machine_is_taken_out_of_service(shopped: Run) -> None:
    result = shopped("shop", "retire", "EQ-001", "--on", "2025-09-01", "--why", "pump seized")
    assert "2025-09-01" in result.output
    later = shopped(
        "shop", "calibrate", "EQ-001", "--on", "2025-09-02", "--flow", "1.5 fl oz", expect=1
    )
    assert later.exit_code != 0
