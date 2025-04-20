from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from dipcount import clock, species
from dipcount.errors import NotFound, UsageError
from dipcount.model.trap import KINDS, Catch, Collection, Trap, trap_kind

LISTED = dt.date(2025, 4, 1)
SET_AT = clock.moment("2025-06-03 16:30")
PULLED = clock.moment("2025-06-04 08:15")


def a_trap(**changes: object) -> Trap:
    fields: dict[str, object] = {
        "id": "TR-0001",
        "zone": "ZN-001",
        "name": "Ambrose gravid 1",
        "kind": "gravid",
        "listed_on": LISTED,
    }
    fields.update(changes)
    return Trap(**fields)  # type: ignore[arg-type]


def a_collection(**changes: object) -> Collection:
    fields: dict[str, object] = {
        "id": "CO-250604-01",
        "trap": "TR-0001",
        "set_at": SET_AT,
        "pulled_at": PULLED,
        "handler": "D. Uzoma",
    }
    fields.update(changes)
    return Collection(**fields)  # type: ignore[arg-type]


def test_every_trap_kind_names_a_lure_and_a_guild() -> None:
    for kind in KINDS.values():
        assert kind.lure
        assert kind.guilds


def test_an_unknown_trap_kind_is_refused() -> None:
    with pytest.raises(UsageError):
        trap_kind("bucket")
    with pytest.raises(UsageError):
        a_trap(kind="bucket")


def test_the_gravid_traps_are_the_ones_that_take_fed_females() -> None:
    gravid = [key for key, kind in KINDS.items() if kind.catches_gravid]
    assert set(gravid) == {"gravid", "resting"}


def test_the_container_species_have_their_own_trap() -> None:
    assert trap_kind("bg").guilds == (species.CONTAINER,)


def test_a_trap_needs_a_name(  # and it is the label on the fence post
) -> None:
    with pytest.raises(UsageError):
        a_trap(name="  ")


def test_a_trap_is_open_between_its_dates() -> None:
    trap = a_trap(retired_on=dt.date(2025, 10, 1))
    assert not trap.is_open(dt.date(2025, 3, 31))
    assert trap.is_open(dt.date(2025, 6, 4))
    assert not trap.is_open(dt.date(2025, 10, 2))


def test_a_trap_cannot_be_retired_before_it_was_listed() -> None:
    with pytest.raises(UsageError):
        a_trap(retired_on=dt.date(2025, 3, 1))


def test_a_catch_takes_a_real_species_and_a_sex() -> None:
    with pytest.raises(UsageError):
        Catch("CXPP", "X", 4)
    with pytest.raises(NotFound):
        Catch("ZZZZ", "F", 4)
    with pytest.raises(UsageError):
        Catch("CXPP", "F", -1)


def test_only_the_females_count() -> None:
    assert Catch("CXPP", "F", 4).counts
    assert not Catch("CXPP", "M", 4).counts


def test_a_night_out_is_one_trap_night() -> None:
    assert a_collection().nights == Decimal("1")


def test_three_nights_out_is_three() -> None:
    longer = a_collection(pulled_at=clock.moment("2025-06-06 16:30"))
    assert longer.nights == Decimal("3")


def test_the_index_is_females_over_nights() -> None:
    found = a_collection(catches=(Catch("CXPP", "F", 42),))
    assert found.females == 42
    assert found.index == Decimal("42")


def test_males_are_recorded_and_left_out_of_the_index() -> None:
    found = a_collection(catches=(Catch("CXPP", "F", 42), Catch("CXPP", "M", 130)))
    assert found.males == 130
    assert found.total == 172
    assert found.index == Decimal("42")


def test_a_longer_set_divides_the_index_down() -> None:
    found = a_collection(
        pulled_at=clock.moment("2025-06-06 16:30"),
        catches=(Catch("CXPP", "F", 42),),
    )
    assert found.index == Decimal("14")


def test_a_trap_that_did_not_run_is_not_a_night_of_nothing() -> None:
    broken = a_collection(worked=False, note="battery flat")
    assert broken.index == 0
    assert broken.total == 0
    with pytest.raises(UsageError, match="did not run"):
        a_collection(worked=False, catches=(Catch("CXPP", "F", 4),))


def test_a_species_index_is_taken_out_of_the_jar() -> None:
    found = a_collection(
        catches=(
            Catch("CXPP", "F", 42),
            Catch("CXTR", "F", 8),
            Catch("AEVX", "F", 200),
        ),
    )
    assert found.females_of("CXTR") == 8
    assert found.index_of("CXTR") == Decimal("8")
    assert found.index == Decimal("250")


def test_the_species_in_the_jar_are_listed() -> None:
    found = a_collection(catches=(Catch("CXTR", "F", 8), Catch("CXPP", "M", 2)))
    assert found.species_seen() == ["CXPP", "CXTR"]


def test_a_collection_needs_a_handler_and_zones_on_its_moments() -> None:
    with pytest.raises(UsageError):
        a_collection(handler=" ")
    with pytest.raises(UsageError):
        a_collection(set_at=SET_AT.replace(tzinfo=None))


def test_a_trap_pulled_before_it_was_set_is_refused() -> None:
    with pytest.raises(UsageError):
        a_collection(pulled_at=SET_AT).nights  # noqa: B018


def test_the_collection_day_is_the_day_it_came_in() -> None:
    found = a_collection()
    assert found.on == dt.date(2025, 6, 4)
    assert found.week == "2025-W23"


def test_the_row_stores_utc_and_the_nights_it_worked_out() -> None:
    row = a_collection().to_row()
    assert str(row["set_at"]).endswith("+00:00")
    assert row["nights"] == 1.0
    assert row["worked"] == 1
