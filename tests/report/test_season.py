from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, formulary, species
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.equipment import FOGGER
from dipcount.model.pool import POSITIVE
from dipcount.model.request import BITING
from dipcount.model.trap import Catch
from dipcount.report import season as report
from dipcount.service import larvicide, requests, survey
from dipcount.store import (
    Book,
    applicators,
    equipment,
    inventory,
    pools,
    sites,
    traps,
    upgrade,
    zones,
)
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)
ON = dt.date(2025, 8, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2025, 9, 1),
    )
    equipment.add(
        book,
        FOGGER,
        "Larkspur",
        "XLR-40",
        "40-11872",
        LISTED,
        nominal=quantity("1.5 fl oz"),
        swath_ft=300.0,
    )
    return book


def positive_week(book: Book, day: str = "2025-06-04") -> None:
    made = traps.record(
        book,
        "TR-0001",
        clock.moment(f"{day} 16:30"),
        clock.moment(f"{day} 23:30"),
        "D. Uzoma",
        catches=[Catch("CXPP", "F", 200)],
    )
    pool = pools.submit(book, made.id, "CXPP", 50, clock.day(day))
    pools.report(book, pool.id, species.WNV, POSITIVE, clock.day(day))


def test_an_empty_season_reads_as_empty(district: Book) -> None:
    found = report.season(district, 2025, on=ON)
    assert found.visits == 0
    assert found.positive_weeks == 0
    assert found.highest_level == "none"
    assert found.first_positive is None


def test_the_season_counts_the_work(district: Book) -> None:
    survey.inspect(district, "K. B", "SI-0001", clock.moment("2025-06-04 09:00"), dips=10)
    larvicide.treat(district, "AP-001", "SI-0001", "LT-0001", clock.moment("2025-06-04 10:40"))
    requests.take(district, "T. O", BITING, "north", clock.moment("2025-06-04 09:15"), "here")
    found = report.season(district, 2025, on=ON)
    assert found.visits == 1
    assert found.treatments == 1
    assert found.calls == 1


def test_the_first_positive_week_is_found(district: Book) -> None:
    positive_week(district, "2025-06-04")
    found = report.season(district, 2025, on=ON)
    assert found.first_positive is not None
    assert found.first_positive.label == "2025-W23"
    assert found.positive_weeks == 1


def test_the_peak_week_is_the_highest_index(district: Book) -> None:
    positive_week(district, "2025-06-04")
    found = report.season(district, 2025, on=ON)
    assert found.peak is not None
    assert found.peak.label == "2025-W23"


def test_the_season_stops_at_the_day_it_is_taken(district: Book) -> None:
    positive_week(district, "2025-06-04")
    early = report.season(district, 2025, on=dt.date(2025, 5, 1))
    assert early.first_positive is None
    assert early.treatments == 0


def test_the_highest_level_is_the_worst_week(district: Book) -> None:
    made = traps.record(
        district,
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        "D. Uzoma",
        catches=[Catch("CXPP", "F", 400)],
    )
    for _ in range(4):
        pool = pools.submit(district, made.id, "CXPP", 50, dt.date(2025, 6, 5))
        pools.report(district, pool.id, species.WNV, POSITIVE, dt.date(2025, 6, 9))
    found = report.season(district, 2025, on=ON)
    assert found.highest_level in {"high", "emergency"}


def test_every_trap_kind_gets_a_mean(district: Book) -> None:
    found = report.season(district, 2025, on=ON)
    assert set(found.indices) == {"light", "gravid", "bg", "resting"}
    assert found.indices["light"] == Decimal(0)


def test_the_mean_leaves_out_the_weeks_with_no_trap_nights(district: Book) -> None:
    positive_week(district, "2025-06-04")
    found = report.season(district, 2025, on=ON)
    assert found.indices["gravid"] > 0


def test_the_report_renders_every_section(district: Book) -> None:
    text = report.season(district, 2025, on=ON).render()
    for heading in ("season to", "weekly picture", "season abundance", "totals"):
        assert heading in text


def test_the_return_travels_with_the_season(district: Book) -> None:
    larvicide.treat(district, "AP-001", "SI-0001", "LT-0001", clock.moment("2025-06-04 10:40"))
    found = report.season(district, 2025, on=ON)
    assert len(found.filed.filed) == 1


def test_the_board_names_a_licence_running_out(district: Book) -> None:
    found = report.board(district, dt.date(2025, 8, 1))
    assert [one.applicator.name for one in found.licences] == ["K. Brennaman"]
    assert "K. Brennaman" in found.render()


def test_the_board_names_a_machine_that_is_due(district: Book) -> None:
    found = report.board(district, dt.date(2025, 8, 1))
    assert [one.machine.model for one in found.machines] == ["XLR-40"]
    assert "never calibrated" in found.render()


def test_a_fresh_calibration_takes_the_machine_off_the_board(district: Book) -> None:
    equipment.calibrate(
        district,
        "EQ-001",
        dt.date(2025, 7, 28),
        "K. B",
        quantity("1.5 fl oz"),
        droplet=17.0,
        speed_mph=10.0,
    )
    found = report.board(district, dt.date(2025, 8, 1), within=0)
    assert found.machines == ()


def test_the_board_counts_the_open_and_late_calls(district: Book) -> None:
    requests.take(district, "T. O", BITING, "north", clock.moment("2025-07-20 09:15"), "here")
    requests.take(district, "T. O", BITING, "north", clock.moment("2025-08-01 09:15"), "there")
    found = report.board(district, dt.date(2025, 8, 1))
    assert found.open_calls == 2
    assert found.late_calls == 1


def test_the_board_renders_the_call_line(district: Book) -> None:
    text = report.board(district, dt.date(2025, 8, 1)).render()
    assert "calls" in text
    assert "late" in text
