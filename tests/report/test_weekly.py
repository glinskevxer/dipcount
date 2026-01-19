from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, formulary, species
from dipcount.model.applicator import AQUATIC, CERTIFIED, CORE, PUBLIC_HEALTH
from dipcount.model.inspection import Tally
from dipcount.model.pool import POSITIVE
from dipcount.model.request import BITING, DEAD_BIRD
from dipcount.model.trap import Catch
from dipcount.report import weekly as report
from dipcount.service import larvicide, requests, survey, trapping
from dipcount.store import Book, applicators, inventory, pools, sites, traps, upgrade, zones
from dipcount.units import quantity

LISTED = dt.date(2025, 3, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    sites.add(book, "north", "Weller Road", "catch_basin", quantity("14 each"), LISTED)
    sites.add(book, "north", "Sawyer marsh", "cattail_marsh", quantity("6 acre"), LISTED)
    sites.add(book, "south", "Rowe bottom", "floodplain", quantity("22 acre"), LISTED)
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    formulary.stock(book, dt.date(2025, 1, 15))
    inventory.receive(book, "Bactilore WSP", "24W-0801", quantity("500 each"), LISTED)
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
    return book


def test_an_empty_week_reads_as_an_empty_week(district: Book) -> None:
    found = report.weekly(district, 2025, 23)
    assert found.label == "2025-W23"
    assert found.start == dt.date(2025, 6, 1)
    assert found.end == dt.date(2025, 6, 7)
    assert found.larval.visits == 0
    assert found.larval.per_dip == 0
    assert found.picture.level == "none"
    assert "2025-W23" in found.render()


def test_the_larval_figures_add_the_week_up(district: Book) -> None:
    survey.inspect(
        district,
        "K. B",
        "SI-0001",
        clock.moment("2025-06-04 09:00"),
        dips=10,
        tallies=(Tally("CXPP", "2", 12),),
    )
    survey.inspect(district, "K. B", "SI-0002", clock.moment("2025-06-05 09:00"), water=False)
    found = report.weekly(district, 2025, 23)
    assert found.larval.visits == 2
    assert found.larval.dry == 1
    assert found.larval.wet == 1
    assert found.larval.positive == 1
    assert found.larval.larvae == 12
    assert found.larval.per_dip == Decimal("1.2")


def test_the_treated_count_is_what_the_rule_book_said(district: Book) -> None:
    survey.inspect(
        district,
        "K. B",
        "SI-0001",
        clock.moment("2025-06-04 09:00"),
        dips=10,
        tallies=(Tally("CXPP", "2", 12),),
    )
    survey.inspect(
        district,
        "K. B",
        "SI-0002",
        clock.moment("2025-06-05 09:00"),
        dips=10,
        tallies=(Tally("AEVX", "2", 1),),
    )
    found = report.weekly(district, 2025, 23)
    assert found.larval.treated == 1


def test_the_positives_are_counted_by_habitat(district: Book) -> None:
    survey.inspect(
        district,
        "K. B",
        "SI-0001",
        clock.moment("2025-06-04 09:00"),
        dips=10,
        tallies=(Tally("CXPP", "2", 12),),
    )
    found = report.weekly(district, 2025, 23)
    assert found.larval.by_habitat == {"catch_basin": 1}
    assert report.busiest_habitat(found) == "catch_basin"


def test_a_week_with_nothing_positive_has_no_busiest_habitat(district: Book) -> None:
    assert report.busiest_habitat(report.weekly(district, 2025, 23)) is None


def test_a_zone_narrows_the_larval_figures(district: Book) -> None:
    survey.inspect(district, "K. B", "SI-0001", clock.moment("2025-06-04 09:00"), dips=10)
    survey.inspect(district, "K. B", "SI-0003", clock.moment("2025-06-04 10:00"), dips=10)
    assert report.weekly(district, 2025, 23).larval.visits == 2
    assert report.weekly(district, 2025, 23, zone_id="ZN-001").larval.visits == 1


def test_every_trap_kind_gets_a_line(district: Book) -> None:
    found = report.weekly(district, 2025, 23)
    assert len(found.indices) == 4
    assert {one.kind for one in found.indices} == {"light", "gravid", "bg", "resting"}


def test_the_trap_figures_come_off_the_jars(district: Book) -> None:
    trapping.collect(
        district,
        "D. Uzoma",
        "TR-0001",
        clock.moment("2025-06-03 16:30"),
        clock.moment("2025-06-04 08:15"),
        catches=(Catch("CXPP", "F", 40),),
    )
    found = report.weekly(district, 2025, 23)
    gravid = next(one for one in found.indices if one.kind == "gravid")
    assert gravid.value == Decimal("40")
    assert report.trap_nights(found) == Decimal("1")
    assert report.collections(district, 2025, 23) == 1


def test_the_virus_section_carries_the_level(district: Book) -> None:
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
    found = report.weekly(district, 2025, 23)
    assert found.picture.positive
    assert found.picture.level in {"high", "emergency"}
    assert "vector index" in found.virus_sheet().render()


def test_the_work_section_counts_acres_and_structures_apart(district: Book) -> None:
    larvicide.treat(district, "AP-001", "SI-0001", "LT-0001", clock.moment("2025-06-04 10:40"))
    larvicide.treat(district, "AP-001", "SI-0002", "LT-0002", clock.moment("2025-06-04 11:40"))
    found = report.weekly(district, 2025, 23)
    assert found.work.treatments == 2
    assert found.work.acres == Decimal(6)
    assert found.work.structures == Decimal(14)


def test_the_products_used_are_totalled(district: Book) -> None:
    larvicide.treat(district, "AP-001", "SI-0002", "LT-0002", clock.moment("2025-06-04 11:40"))
    found = report.weekly(district, 2025, 23)
    assert "PD-0001" in found.work.by_product
    assert "lb" in found.work.by_product["PD-0001"]


def test_the_calls_are_counted_by_kind(district: Book) -> None:
    requests.take(district, "T. O", BITING, "north", clock.moment("2025-06-04 09:15"), "here")
    requests.take(district, "T. O", DEAD_BIRD, "north", clock.moment("2025-06-05 09:15"), "there")
    found = report.weekly(district, 2025, 23)
    assert found.calls.taken == 2
    assert found.calls.by_kind == {BITING: 1, DEAD_BIRD: 1}


def test_the_calls_narrow_to_a_zone(district: Book) -> None:
    requests.take(district, "T. O", BITING, "north", clock.moment("2025-06-04 09:15"), "here")
    requests.take(district, "T. O", BITING, "south", clock.moment("2025-06-04 09:15"), "there")
    assert report.weekly(district, 2025, 23, zone_id="ZN-002").calls.taken == 1


def test_the_report_renders_every_section(district: Book) -> None:
    text = report.weekly(district, 2025, 23).render()
    for heading in ("larval surveillance", "adult surveillance", "work done", "calls"):
        assert heading in text


def test_a_zone_report_says_which_zone(district: Book) -> None:
    text = report.weekly(district, 2025, 23, zone_id="ZN-001").render()
    assert "zone ZN-001" in text


def test_every_sheet_comes_back_in_order(district: Book) -> None:
    found = report.weekly(district, 2025, 23)
    assert len(found.sheets()) == 7
