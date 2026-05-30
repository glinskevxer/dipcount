"""A season, start to finish, against a book made for the purpose.

The tests each check one thing and mock nothing, which is the right way round,
but between them they never do the whole of a season in order. This does: open
a book, lay out the district, hire somebody, stock the shelf, work the larval
round, treat what wants treating, run the traps, send the pools, read the
week, fog a block, and file the return.

It runs after installation in ci, which is the only way to catch a package
that tests green from a checkout and is missing a module in the wheel.
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

from dipcount import clock, formulary, species
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.bioassay import CONTROL, FIELD, Reading
from dipcount.model.block import PHONE
from dipcount.model.equipment import FOGGER
from dipcount.model.exclusion import APIARY
from dipcount.model.inspection import Tally
from dipcount.model.pool import POSITIVE
from dipcount.model.request import BITING
from dipcount.model.trap import Catch
from dipcount.report import season as season_report
from dipcount.report import use_report, weekly
from dipcount.service import adulticide, larvicide, requests, survey, trapping
from dipcount.store import (
    Book,
    applicators,
    bioassays,
    blocks,
    equipment,
    exclusions,
    inventory,
    pools,
    sites,
    traps,
    upgrade,
    weather,
    zones,
)
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


def _lay_out(book: Book) -> None:
    zones.add(book, "north", "R. Vandeburg")
    zones.add(book, "south", "T. Okwuosa")
    sites.add(book, "north", "Weller Road basins", "catch_basin", quantity("14 each"), LISTED)
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    blocks.add(book, "north", "Ardmore east grid", 640.0, LISTED, road_miles=18.4)
    exclusions.add(book, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    blocks.link(book, "BK-0001", "EX-0001")
    weather.add_station(book, "Ambrose airport", "north", dt.date(2025, 1, 1))
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
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    inventory.receive(book, "Kestrel ULV", "25K-0114", quantity("30 gal"), LISTED)


def _work_the_round(book: Book) -> None:
    weather.record(book, "ST-0001", dt.date(2025, 6, 3), 84.0, 62.0, rain_in=0.6)
    made, found = survey.inspect(
        book,
        "K. Brennaman",
        "SI-0002",
        clock.moment("2025-06-04 09:00"),
        dips=10,
        tallies=(Tally("CXPP", "2", 12),),
    )
    if not found.treatable:
        message = f"{made.id} should have wanted treating"
        raise AssertionError(message)
    larvicide.treat(book, "AP-001", "SI-0002", "LT-0001", clock.moment("2025-06-04 10:40"))
    requests.take(
        book,
        "T. Okwuosa",
        BITING,
        "north",
        clock.moment("2025-06-04 09:15"),
        "1400 Weir Street",
    )


def _run_the_traps(book: Book) -> None:
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    jar = trapping.collect(
        book,
        "D. Uzoma",
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        catches=(Catch("CXPP", "F", 120),),
    )
    for _ in range(2):
        pool = pools.submit(book, jar.id, "CXPP", 50, dt.date(2025, 6, 5))
        pools.report(book, pool.id, species.WNV, POSITIVE, dt.date(2025, 6, 9))
    index = trapping.week_index(book, 2025, 23, "gravid")
    if index.value <= 0:
        message = "the trap index should not be nothing"
        raise AssertionError(message)


def _fog_a_block(book: Book) -> None:
    blocks.give(
        book,
        "EX-0001",
        "BK-0001",
        clock.moment("2025-07-08 09:00"),
        clock.moment("2025-07-10 20:00"),
        clock.moment("2025-07-11 02:00"),
        PHONE,
        "T. Okwuosa",
    )
    equipment.calibrate(
        book,
        "EQ-001",
        dt.date(2025, 7, 9),
        "K. Brennaman",
        quantity("1.5 fl oz"),
        droplet=17.0,
        speed_mph=10.0,
    )
    adulticide.spray(
        book,
        "AP-001",
        "BK-0001",
        "LT-0002",
        clock.moment("2025-07-10 21:10"),
        clock.moment("2025-07-10 22:40"),
        quantity("1.4 gal"),
        wind_mph=4.5,
        temperature=74.0,
        wind_from="SW",
    )


def _assay(book: Book) -> None:
    bioassays.start(
        book,
        "permethrin",
        "CXPP",
        FIELD,
        dt.date(2025, 8, 12),
        "K. Brennaman",
        43.0,
        30,
        zone_id="north",
        readings=[
            *[Reading(str(one + 1), 30, 20, 25) for one in range(4)],
            Reading(CONTROL, 30, 1, 25),
        ],
    )


def _read_the_reports(book: Book, quiet: bool) -> None:
    week = weekly.weekly(book, 2025, 23)
    filed = use_report.season(book, 2025)
    board = season_report.board(book, dt.date(2025, 8, 1))
    shape = season_report.season(book, 2025, on=dt.date(2025, 8, 1))
    if len(filed.filed) != 2:
        message = f"the return should carry two applications, not {len(filed.filed)}"
        raise AssertionError(message)
    if shape.first_positive is None:
        message = "the season should have a first positive week"
        raise AssertionError(message)
    if not quiet:
        print(week.render())
        print(filed.render())
        print(board.render())


def run(quiet: bool = False) -> Path:
    """Work a season through, and say which book it happened in."""
    into = Path(tempfile.mkdtemp(prefix="dipcount-smoke-")) / "district.sqlite3"
    book = Book.create(into)
    try:
        upgrade(book)
        _lay_out(book)
        _work_the_round(book)
        _run_the_traps(book)
        _fog_a_block(book)
        _assay(book)
        _read_the_reports(book, quiet)
    finally:
        book.close()
    return into


def main(argv: list[str] | None = None) -> None:
    """Run the smoke test."""
    args = sys.argv[1:] if argv is None else argv
    quiet = "--quiet" in args
    made = run(quiet=quiet)
    print(f"smoke: a season worked through in {made}")


if __name__ == "__main__":
    main()
