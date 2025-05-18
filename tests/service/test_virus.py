from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, rules, species
from dipcount.model.pool import NEGATIVE, POSITIVE, UNSATISFACTORY
from dipcount.model.trap import Catch
from dipcount.service import virus
from dipcount.store import Book, pools, traps, upgrade, zones

LISTED = dt.date(2025, 4, 1)


@pytest.fixture
def district(book: Book) -> Book:
    upgrade(book)
    zones.add(book, "north")
    zones.add(book, "south")
    traps.add(book, "north", "Ambrose gravid 1", "gravid", LISTED)
    traps.add(book, "south", "Rowe gravid 1", "gravid", LISTED)
    return book


def jar(book: Book, trap: str, day: int, catches: list[Catch]) -> str:
    made = traps.record(
        book,
        trap,
        clock.moment(f"2025-06-{day - 1:02d} 16:30"),
        clock.moment(f"2025-06-{day:02d} 08:15"),
        "D. Uzoma",
        catches=catches,
    )
    return made.id


def send(
    book: Book,
    collection: str,
    code: str,
    size: int,
    outcome: str | None = None,
    virus_name: str = species.WNV,
) -> str:
    made = pools.submit(book, collection, code, size, dt.date(2025, 6, 6))
    if outcome is not None:
        pools.report(book, made.id, virus_name, outcome, dt.date(2025, 6, 9))
    return made.id


def test_a_week_with_no_pools_has_no_rate(district: Book) -> None:
    found = virus.picture(district, 2025, 23, species.WNV)
    assert not found.rate.usable
    assert found.vector_index == 0
    assert found.level == "none"
    assert not found.positive


def test_pools_are_keyed_on_the_week_the_jar_was_pulled(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    pools.submit(district, collection, "CXPP", 50, dt.date(2025, 6, 20))
    assert len(virus.pools_in_week(district, 2025, 23)) == 1
    assert len(virus.pools_in_week(district, 2025, 25)) == 0


def test_a_positive_pool_gives_a_rate_and_an_index(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    send(district, collection, "CXPP", 50, POSITIVE)
    send(district, collection, "CXPP", 50, NEGATIVE)
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.positive
    assert found.rate.rate > 0
    assert found.abundance.value == Decimal("100")
    assert found.vector_index > 0


def test_the_minimum_rate_sits_under_the_estimate(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    send(district, collection, "CXPP", 50, POSITIVE)
    send(district, collection, "CXPP", 50, NEGATIVE)
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.minimum < found.rate.rate


def test_a_pool_of_something_that_cannot_carry_is_held_back(district: Book) -> None:
    collection = jar(
        district,
        "TR-0001",
        4,
        [Catch("CXPP", "F", 100), Catch("AEVX", "F", 100)],
    )
    send(district, collection, "CXPP", 50, POSITIVE)
    send(district, collection, "AEVX", 50, NEGATIVE)
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.pools_held == 1
    assert found.rate.pools == 1
    assert "virus.pools" in found.reasons


def test_the_held_back_pool_would_have_dragged_the_rate_down(district: Book) -> None:
    collection = jar(
        district,
        "TR-0001",
        4,
        [Catch("CXPP", "F", 100), Catch("AEVX", "F", 100)],
    )
    send(district, collection, "CXPP", 50, POSITIVE)
    send(district, collection, "AEVX", 50, NEGATIVE)
    only_vectors = virus.picture(district, 2025, 23, species.WNV).rate.rate
    from dipcount import estimate

    with_everything = estimate.estimate([50, 50], [True, False]).rate
    assert only_vectors > with_everything


def test_an_unreadable_pool_is_held_back_too(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    send(district, collection, "CXPP", 50, POSITIVE)
    send(district, collection, "CXPP", 50, UNSATISFACTORY)
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.pools_held == 1
    assert found.rate.pools == 1


def test_a_pool_still_out_at_the_lab_is_held_back(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    send(district, collection, "CXPP", 50, POSITIVE)
    send(district, collection, "CXPP", 50)
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.pools_held == 1


def test_a_result_for_one_virus_does_not_answer_another(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXSA", "F", 100)])
    send(district, collection, "CXSA", 50, POSITIVE, species.WNV)
    west_nile = virus.picture(district, 2025, 23, species.WNV)
    eastern = virus.picture(district, 2025, 23, species.EEE)
    assert west_nile.positive
    assert not eastern.positive
    assert eastern.pools_held == 1


def test_the_abundance_takes_only_the_vector_species(district: Book) -> None:
    jar(district, "TR-0001", 4, [Catch("CXPP", "F", 40), Catch("AEVX", "F", 400)])
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.abundance.value == Decimal("40")


def test_a_zone_narrows_both_halves(district: Book) -> None:
    north = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    south = jar(district, "TR-0002", 4, [Catch("CXPP", "F", 60)])
    send(district, north, "CXPP", 50, POSITIVE)
    send(district, south, "CXPP", 50, NEGATIVE)
    both = virus.picture(district, 2025, 23, species.WNV)
    only_north = virus.picture(district, 2025, 23, species.WNV, zone_id="ZN-001")
    assert both.rate.pools == 2
    assert only_north.rate.pools == 1
    assert only_north.abundance.value == Decimal("100")
    assert only_north.vector_index > both.vector_index


def test_the_level_climbs_with_the_index() -> None:
    assert rules.response_level(Decimal(0)) == "none"
    assert rules.response_level(Decimal("0.1")) == "low"
    assert rules.response_level(Decimal("0.3")) == "moderate"
    assert rules.response_level(Decimal("1.0")) == "high"
    assert rules.response_level(Decimal("2.0")) == "emergency"


def test_the_ladder_is_in_order() -> None:
    floors = [floor for _, floor in rules.ladder()]
    assert floors == sorted(floors)


def test_a_busy_week_puts_the_district_up_the_ladder(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 500)])
    for _ in range(4):
        send(district, collection, "CXPP", 50, POSITIVE)
    found = virus.picture(district, 2025, 23, species.WNV)
    assert found.level in {"high", "emergency"}
    assert "emergency" in found.line() or "high" in found.line()


def test_the_first_positive_week_of_a_season_is_found(district: Book) -> None:
    collection = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 100)])
    send(district, collection, "CXPP", 50, POSITIVE)
    found = virus.first_positive(district, 2025, species.WNV)
    assert found is not None
    assert found.week == 23


def test_a_season_with_nothing_positive_has_no_first_week(district: Book) -> None:
    assert virus.first_positive(district, 2025, species.WNV, last=26) is None


def test_the_peak_week_is_the_highest_index(district: Book) -> None:
    quiet = jar(district, "TR-0001", 4, [Catch("CXPP", "F", 60)])
    send(district, quiet, "CXPP", 50, POSITIVE)
    busy = traps.record(
        district,
        "TR-0001",
        clock.moment("2025-06-10 16:30"),
        clock.moment("2025-06-11 08:15"),
        "D. Uzoma",
        catches=[Catch("CXPP", "F", 400)],
    )
    pools.report(
        district,
        pools.submit(district, busy.id, "CXPP", 50, dt.date(2025, 6, 13)).id,
        species.WNV,
        POSITIVE,
        dt.date(2025, 6, 16),
    )
    top = virus.peak(district, 2025, species.WNV, first=22, last=26)
    assert top is not None
    assert top.week == 24


def test_a_season_with_no_index_has_no_peak(district: Book) -> None:
    assert virus.peak(district, 2025, species.WNV, first=22, last=26) is None


def test_a_season_runs_a_week_at_a_time(district: Book) -> None:
    weeks = virus.season(district, 2025, species.WNV, first=22, last=25)
    assert [one.week for one in weeks] == [22, 23, 24, 25]
    assert all(one.virus == species.WNV for one in weeks)
