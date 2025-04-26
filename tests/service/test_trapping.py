from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, rules, species
from dipcount.model.trap import KINDS, Catch
from dipcount.service import trapping
from dipcount.store import Book, traps, upgrade, zones

LISTED = dt.date(2024, 4, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    traps.add(book, "north", "Kettle light 1", "light", LISTED)
    return book


def pull(
    book: Book,
    trap: str,
    on: dt.date,
    catches: list[Catch],
    *,
    worked: bool = True,
    nights: int = 1,
) -> None:
    set_at = clock.moment(f"{(on - dt.timedelta(days=nights)).isoformat()} 16:30")
    pulled = clock.moment(f"{on.isoformat()} 08:15")
    traps.record(book, trap, set_at, pulled, "D. Uzoma", worked=worked, catches=catches)


def test_a_week_with_nothing_in_it_is_zero_and_not_an_error(district: Book) -> None:
    found = trapping.week_index(district, 2025, 23, "gravid")
    assert found.value == 0
    assert found.collections == 0
    assert not found.over


def test_the_index_is_females_over_nights(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    pull(district, "TR-0001", dt.date(2025, 6, 6), [Catch("CXPP", "F", 20)])
    found = trapping.week_index(district, 2025, 23, "gravid")
    assert found.females == 60
    assert found.nights == Decimal("2")
    assert found.value == Decimal("30")


def test_males_never_reach_the_index(district: Book) -> None:
    pull(
        district,
        "TR-0001",
        dt.date(2025, 6, 4),
        [Catch("CXPP", "F", 40), Catch("CXPP", "M", 400)],
    )
    assert trapping.week_index(district, 2025, 23, "gravid").value == Decimal("40")


def test_a_trap_that_did_not_run_leaves_both_halves(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    pull(district, "TR-0001", dt.date(2025, 6, 6), [], worked=False)
    found = trapping.week_index(district, 2025, 23, "gravid")
    assert found.nights == Decimal("1")
    assert found.value == Decimal("40")
    assert found.dropped == 1


def test_a_night_of_genuine_zero_does_pull_the_index_down(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    pull(district, "TR-0001", dt.date(2025, 6, 6), [])
    found = trapping.week_index(district, 2025, 23, "gravid")
    assert found.nights == Decimal("2")
    assert found.value == Decimal("20")
    assert found.dropped == 0


def test_the_kinds_are_not_added_together(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    pull(district, "TR-0002", dt.date(2025, 6, 4), [Catch("AEVX", "F", 400)])
    gravid = trapping.week_index(district, 2025, 23, "gravid")
    light = trapping.week_index(district, 2025, 23, "light")
    assert gravid.value == Decimal("40")
    assert light.value == Decimal("400")


def test_each_kind_has_its_own_figure(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    pull(district, "TR-0002", dt.date(2025, 6, 4), [Catch("AEVX", "F", 40)])
    assert trapping.week_index(district, 2025, 23, "gravid").over
    assert not trapping.week_index(district, 2025, 23, "light").over


def test_one_species_can_be_taken_out_of_the_jar(district: Book) -> None:
    pull(
        district,
        "TR-0002",
        dt.date(2025, 6, 4),
        [Catch("AEVX", "F", 400), Catch("CXTR", "F", 20)],
    )
    found = trapping.week_index(district, 2025, 23, "light", code="CXTR")
    assert found.value == Decimal("20")
    assert "CXTR" in found.line()


def test_a_zone_narrows_the_traps(district: Book) -> None:
    traps.add(district, "south", "Rowe gravid 1", "gravid", LISTED)
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    pull(district, "TR-0003", dt.date(2025, 6, 4), [Catch("CXPP", "F", 4)])
    both = trapping.week_index(district, 2025, 23, "gravid")
    north = trapping.week_index(district, 2025, 23, "gravid", zone_id="ZN-001")
    assert both.value == Decimal("22")
    assert north.value == Decimal("40")


def test_a_first_season_has_no_baseline(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    found = trapping.trend(district, 2025, 23, "gravid")
    assert not found.has_baseline
    assert found.ratio is None
    assert not found.elevated
    assert "no baseline" in found.line()


def test_a_baseline_comes_off_the_same_week_in_earlier_seasons(district: Book) -> None:
    pull(
        district,
        "TR-0001",
        clock.week_start(2024, 23) + dt.timedelta(days=3),
        [
            Catch("CXPP", "F", 10),
        ],
    )
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 40)])
    found = trapping.trend(district, 2025, 23, "gravid")
    assert found.baseline == Decimal("10")
    assert found.years == (2024,)
    assert found.ratio == Decimal("4")
    assert found.elevated
    assert "4.00 times the usual" in found.line()


def test_a_week_at_the_usual_level_is_not_elevated(district: Book) -> None:
    pull(
        district,
        "TR-0001",
        clock.week_start(2024, 23) + dt.timedelta(days=3),
        [
            Catch("CXPP", "F", 40),
        ],
    )
    pull(district, "TR-0001", dt.date(2025, 6, 4), [Catch("CXPP", "F", 50)])
    found = trapping.trend(district, 2025, 23, "gravid")
    assert not found.elevated
    assert "ordinary" in found.line()


def test_a_season_with_no_collections_that_week_is_left_out_of_the_baseline(
    district: Book,
) -> None:
    pull(
        district,
        "TR-0001",
        clock.week_start(2024, 23) + dt.timedelta(days=3),
        [
            Catch("CXPP", "F", 10),
        ],
    )
    found = trapping.trend(district, 2025, 23, "gravid", seasons=3)
    assert found.seasons == 1
    assert found.baseline == Decimal("10")


def test_a_season_runs_a_week_at_a_time(district: Book) -> None:
    weeks = trapping.season(district, 2025, "gravid", first=20, last=24)
    assert [one.week for one in weeks] == [20, 21, 22, 23, 24]
    assert all(one.kind == "gravid" for one in weeks)


def test_the_vector_index_takes_only_what_carries_the_virus(district: Book) -> None:
    pull(
        district,
        "TR-0001",
        dt.date(2025, 6, 4),
        [Catch("CXPP", "F", 30), Catch("AEVX", "F", 500)],
    )
    found = trapping.vector_index(district, 2025, 23, species.WNV)
    assert found.females == 30
    assert found.value == Decimal("30")
    assert found.species == species.WNV


def test_the_trap_round_names_what_has_not_been_run(district: Book) -> None:
    pull(district, "TR-0001", dt.date(2025, 6, 4), [])
    waiting = trapping.due(district, dt.date(2025, 6, 8))
    assert [one.id for one in waiting] == ["TR-0002"]
    later = trapping.due(district, dt.date(2025, 6, 12))
    assert [one.id for one in later] == ["TR-0001", "TR-0002"]


def test_every_trap_kind_has_a_figure() -> None:
    assert set(rules.adult_thresholds()) == set(KINDS)
