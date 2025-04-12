from __future__ import annotations

import pytest

from tests.cli.conftest import Run


@pytest.fixture
def watched(started: Run) -> Run:
    started("wx", "station", "Ambrose airport", "north", "--opened", "2025-01-01")
    started(
        "site",
        "add",
        "north",
        "Kettle bottom",
        "--habitat",
        "floodplain",
        "--extent",
        "40 acre",
        "--on",
        "2025-03-01",
    )
    return started


def fill(run: Run, days: list[str], high: str = "80", low: str = "60") -> None:
    for day in days:
        run("wx", "record", "ST-0001", "--on", day, "--high", high, "--low", low)


def test_a_station_is_added_and_listed(watched: Run) -> None:
    result = watched("wx", "stations")
    assert "ST-0001" in result.output
    assert "Ambrose airport" in result.output


def test_a_reading_reports_its_units(watched: Run) -> None:
    result = watched("wx", "record", "ST-0001", "--on", "2025-06-04", "--high", "84", "--low", "62")
    assert "WX-250604-01" in result.output
    assert "23 units" in result.output


def test_a_second_reading_for_a_day_is_refused(watched: Run) -> None:
    watched("wx", "record", "ST-0001", "--on", "2025-06-04", "--high", "84", "--low", "62")
    result = watched(
        "wx",
        "record",
        "ST-0001",
        "--on",
        "2025-06-04",
        "--high",
        "85",
        "--low",
        "63",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_day_shows_every_station(watched: Run) -> None:
    watched("wx", "station", "Rowe levee", "south", "--opened", "2025-01-01")
    watched("wx", "record", "ST-0001", "--on", "2025-06-04", "--high", "84", "--low", "62")
    watched("wx", "record", "ST-0002", "--on", "2025-06-04", "--high", "82", "--low", "61")
    result = watched("wx", "day", "--on", "2025-06-04")
    assert "2 rows" in result.output


def test_the_units_over_a_window_add_up(watched: Run) -> None:
    fill(watched, ["2025-06-01", "2025-06-02", "2025-06-03"])
    result = watched("wx", "units", "ST-0001", "--from", "2025-06-01", "--to", "2025-06-03")
    assert "units" in result.output
    assert "60" in result.output
    assert "none" in result.output


def test_a_gap_is_named_in_the_window(watched: Run) -> None:
    fill(watched, ["2025-06-01", "2025-06-03"])
    result = watched("wx", "units", "ST-0001", "--from", "2025-06-01", "--to", "2025-06-03")
    assert "2025-06-02" in result.output


def test_a_strict_window_refuses_a_gap(watched: Run) -> None:
    fill(watched, ["2025-06-01", "2025-06-03"])
    result = watched(
        "wx",
        "units",
        "ST-0001",
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-03",
        "--strict",
        expect=1,
    )
    assert result.exit_code != 0


def test_the_method_is_named_in_the_output(watched: Run) -> None:
    fill(watched, ["2025-06-01"], high="70", low="38")
    plain = watched(
        "wx",
        "units",
        "ST-0001",
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-01",
        "--method",
        "average",
    )
    modified = watched(
        "wx",
        "units",
        "ST-0001",
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-01",
        "--method",
        "modified",
    )
    assert "average" in plain.output
    assert "modified" in modified.output
    assert plain.output != modified.output


def test_an_unknown_method_is_refused_by_the_option(watched: Run) -> None:
    result = watched(
        "wx",
        "units",
        "ST-0001",
        "--from",
        "2025-06-01",
        "--to",
        "2025-06-01",
        "--method",
        "guesswork",
        expect=2,
    )
    assert result.exit_code != 0


def test_the_forecast_covers_every_guild(watched: Run) -> None:
    fill(watched, [f"2025-06-{day:02d}" for day in range(1, 21)])
    result = watched("wx", "forecast", "ST-0001", "--laid", "2025-06-01")
    assert "floodwater" in result.output
    assert "container" in result.output
    assert "4 rows" in result.output


def test_a_soaking_puts_the_floodwater_sites_on_the_round(watched: Run) -> None:
    watched(
        "wx",
        "record",
        "ST-0001",
        "--on",
        "2025-06-02",
        "--high",
        "80",
        "--low",
        "60",
        "--rain",
        "0.7",
    )
    result = watched("wx", "flood", "--on", "2025-06-04")
    assert "SI-0001" in result.output
    assert "1 row" in result.output


def test_a_light_shower_puts_nothing_on_the_round(watched: Run) -> None:
    watched(
        "wx",
        "record",
        "ST-0001",
        "--on",
        "2025-06-02",
        "--high",
        "80",
        "--low",
        "60",
        "--rain",
        "0.2",
    )
    result = watched("wx", "flood", "--on", "2025-06-04")
    assert "0 rows" in result.output


def test_the_rain_over_a_window_is_totalled(watched: Run) -> None:
    watched(
        "wx",
        "record",
        "ST-0001",
        "--on",
        "2025-06-02",
        "--high",
        "80",
        "--low",
        "60",
        "--rain",
        "0.7",
    )
    watched(
        "wx",
        "record",
        "ST-0001",
        "--on",
        "2025-06-03",
        "--high",
        "80",
        "--low",
        "60",
        "--rain",
        "0.2",
    )
    result = watched("wx", "rain", "ST-0001", "--from", "2025-06-01", "--to", "2025-06-05")
    assert "0.9 inches" in result.output
    assert "1 row" in result.output


def test_a_station_is_closed(watched: Run) -> None:
    result = watched("wx", "close", "ST-0001", "--on", "2025-10-01")
    assert "2025-10-01" in result.output
