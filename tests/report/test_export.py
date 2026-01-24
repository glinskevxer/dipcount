from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest

from dipcount import clock, formulary, species
from dipcount.errors import NotFound
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.exclusion import APIARY
from dipcount.model.inspection import Tally
from dipcount.model.pool import POSITIVE
from dipcount.model.request import BITING
from dipcount.model.trap import Catch
from dipcount.report import export
from dipcount.service import larvicide, requests, survey, trapping
from dipcount.store import (
    Book,
    applicators,
    blocks,
    exclusions,
    inventory,
    pools,
    sites,
    traps,
    upgrade,
    zones,
)
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)
WINDOW = (dt.date(2025, 1, 1), dt.date(2025, 12, 31))


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    sites.add(
        book,
        "north",
        "Sawyer marsh",
        "cattail_marsh",
        quantity("6 acre"),
        LISTED,
        latitude=41.8781,
        longitude=-93.0977,
    )
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    blocks.add(book, "north", "Ardmore east grid", 640.0, LISTED)
    exclusions.add(book, APIARY, "Ferrand apiary", "north", LISTED, contact="M. Ferrand")
    blocks.link(book, "BK-0001", "EX-0001")
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore G", "24G-1187", quantity("400 lb"), LISTED)
    applicators.add(
        book,
        "K. Brennaman",
        "PA-44192",
        CERTIFIED,
        (CORE, PUBLIC_HEALTH, AQUATIC),
        dt.date(2024, 3, 1),
        dt.date(2027, 3, 1),
    )
    survey.inspect(
        book,
        "K. B",
        "SI-0001",
        clock.moment("2025-06-04 09:00"),
        dips=10,
        tallies=(Tally("CXPP", "2", 12),),
    )
    made = trapping.collect(
        book,
        "D. Uzoma",
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        catches=(Catch("CXPP", "F", 60),),
    )
    pool = pools.submit(book, made.id, "CXPP", 50, dt.date(2025, 6, 5))
    pools.report(book, pool.id, species.WNV, POSITIVE, dt.date(2025, 6, 9))
    larvicide.treat(book, "AP-001", "SI-0001", "LT-0001", clock.moment("2025-06-04 10:40"))
    requests.take(book, "T. O", BITING, "north", clock.moment("2025-06-04 09:15"), "here")
    return book


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(text.splitlines()))


def test_every_register_has_a_name(district: Book) -> None:
    assert "sites" in export.names()
    assert "treatments" in export.names()
    assert len(export.names()) == 12


def test_an_unknown_register_is_not_found(district: Book) -> None:
    with pytest.raises(NotFound):
        export.sheet_for(district, "nothing", WINDOW)


def test_the_site_list_comes_out_with_its_coordinates(district: Book) -> None:
    found = rows(export.sheet_for(district, "sites", WINDOW).csv())
    assert found[0][0] == "site"
    assert found[1][0] == "SI-0001"
    assert found[1][7].startswith("41.878")


def test_the_inspection_export_carries_the_week(district: Book) -> None:
    found = rows(export.sheet_for(district, "inspections", WINDOW).csv())
    assert "week" in found[0]
    assert "2025-W23" in found[1]


def test_the_collection_export_carries_the_index(district: Book) -> None:
    found = rows(export.sheet_for(district, "collections", WINDOW).csv())
    assert found[1][-1] == "60.00"


def test_the_pool_export_has_a_column_for_every_virus(district: Book) -> None:
    found = rows(export.sheet_for(district, "pools", WINDOW).csv())
    for virus in species.viruses():
        assert virus in found[0]
    assert "positive" in found[1]


def test_the_treatment_export_carries_the_licence(district: Book) -> None:
    found = rows(export.sheet_for(district, "treatments", WINDOW).csv())
    assert "PA-44192" in found[1]


def test_the_register_export_names_the_blocks(district: Book) -> None:
    found = rows(export.sheet_for(district, "register", WINDOW).csv())
    assert "BK-0001" in found[1]


def test_the_crew_export_spells_the_categories_out(district: Book) -> None:
    found = rows(export.sheet_for(district, "crew", WINDOW).csv())
    assert "core public health aquatic" in " ".join(found[1])


def test_the_lot_export_says_what_is_left(district: Book) -> None:
    found = rows(export.sheet_for(district, "lots", WINDOW).csv())
    assert found[1][-1] == "362.5 lb"


def test_a_window_cuts_the_windowed_exports(district: Book) -> None:
    narrow = (dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert len(rows(export.sheet_for(district, "treatments", narrow).csv())) == 1


def test_a_window_does_not_cut_the_registers(district: Book) -> None:
    narrow = (dt.date(2025, 7, 1), dt.date(2025, 7, 31))
    assert len(rows(export.sheet_for(district, "sites", narrow).csv())) == 2


def test_one_register_is_written_to_a_file(district: Book, tmp_path: Path) -> None:
    path = export.write(district, "sites", WINDOW, tmp_path / "out")
    assert path.name == "sites.csv"
    assert "SI-0001" in path.read_text()


def test_every_register_is_written_to_a_directory(district: Book, tmp_path: Path) -> None:
    made = export.write_all(district, WINDOW, tmp_path / "out")
    assert len(made) == len(export.names())
    assert {one.name for one in made} == {f"{name}.csv" for name in export.names()}
    for one in made:
        assert one.read_text().splitlines()


def test_the_directory_is_made_if_it_is_not_there(district: Book, tmp_path: Path) -> None:
    into = tmp_path / "deep" / "down"
    export.write(district, "sites", WINDOW, into)
    assert into.exists()


def test_every_export_has_a_heading_row(district: Book) -> None:
    for name in export.names():
        found = rows(export.sheet_for(district, name, WINDOW).csv())
        assert found
        assert all(cell for cell in found[0])
