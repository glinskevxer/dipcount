from __future__ import annotations

from decimal import Decimal

import pytest

from dipcount import clock
from dipcount.errors import UsageError
from dipcount.model.inspection import Inspection, Tally, stage_name

AT = clock.moment("2025-06-04 09:15")


def an_inspection(**changes: object) -> Inspection:
    fields: dict[str, object] = {
        "id": "IN-250604-01",
        "site": "SI-0001",
        "at": AT,
        "inspector": "K. Brennaman",
        "water": True,
        "dips": 10,
    }
    fields.update(changes)
    return Inspection(**fields)  # type: ignore[arg-type]


def test_the_stages_are_the_ones_the_bench_writes() -> None:
    assert stage_name("R") == "egg raft"
    assert stage_name("P") == "pupa"
    assert stage_name("3") == "instar 3"


def test_a_tally_takes_a_real_stage() -> None:
    with pytest.raises(UsageError):
        Tally("CXPP", "5", 4)
    with pytest.raises(UsageError):
        Tally("CXPP", "1", -1)


def test_only_the_instars_are_larval() -> None:
    assert Tally("CXPP", "2", 4).is_larval
    assert not Tally("CXPP", "P", 4).is_larval
    assert not Tally("CXPP", "R", 4).is_larval


def test_a_dry_site_cannot_have_been_dipped() -> None:
    with pytest.raises(UsageError, match="dry site"):
        an_inspection(water=False)


def test_a_dry_site_is_a_complete_record() -> None:
    dry = an_inspection(water=False, dips=0)
    assert not dry.positive
    assert dry.per_dip == 0


def test_larvae_without_dips_is_refused() -> None:
    with pytest.raises(UsageError, match="no dips"):
        an_inspection(dips=0, tallies=(Tally("CXPP", "2", 4),))


def test_an_inspection_needs_an_inspector_and_a_zone() -> None:
    with pytest.raises(UsageError):
        an_inspection(inspector="  ")
    with pytest.raises(UsageError):
        an_inspection(at=AT.replace(tzinfo=None))


def test_larvae_per_dip_is_larvae_over_dips() -> None:
    found = an_inspection(
        dips=10,
        tallies=(Tally("CXPP", "1", 12), Tally("CXPP", "3", 8)),
    )
    assert found.larvae == 20
    assert found.per_dip == Decimal(2)


def test_pupae_do_not_count_towards_larvae_per_dip() -> None:
    found = an_inspection(
        dips=10,
        tallies=(Tally("CXPP", "2", 10), Tally("CXPP", "P", 30)),
    )
    assert found.larvae == 10
    assert found.pupae == 30
    assert found.per_dip == Decimal(1)


def test_the_pupal_share_says_how_much_of_the_brood_is_gone() -> None:
    found = an_inspection(
        dips=10,
        tallies=(Tally("CXPP", "4", 25), Tally("CXPP", "P", 75)),
    )
    assert found.pupal_share == Decimal("0.75")


def test_the_late_share_is_the_third_and_fourth_instars() -> None:
    found = an_inspection(
        dips=10,
        tallies=(
            Tally("CXPP", "1", 10),
            Tally("CXPP", "3", 20),
            Tally("CXPP", "4", 10),
        ),
    )
    assert found.late_share == Decimal("0.75")


def test_shares_of_nothing_are_zero_and_not_an_error() -> None:
    empty = an_inspection(dips=10)
    assert empty.pupal_share == 0
    assert empty.late_share == 0
    assert empty.per_dip == 0


def test_egg_rafts_count_as_positive_without_being_larvae() -> None:
    found = an_inspection(dips=10, tallies=(Tally("CXPP", "R", 3),))
    assert found.rafts == 3
    assert found.larvae == 0
    assert found.positive


def test_species_are_listed_and_counted_apart() -> None:
    found = an_inspection(
        dips=20,
        tallies=(
            Tally("CXPP", "2", 30),
            Tally("CXRS", "2", 10),
            Tally("", "3", 5),
        ),
    )
    assert found.species_seen() == ["CXPP", "CXRS"]
    assert found.by_species("CXPP") == 30
    assert found.by_species("CXRS") == 10
    assert found.larvae == 45


def test_the_day_and_the_week_come_off_the_moment() -> None:
    found = an_inspection()
    assert found.on.isoformat() == "2025-06-04"
    assert found.week == "2025-W23"


def test_the_row_stores_utc_and_a_flag_as_an_integer() -> None:
    row = an_inspection().to_row()
    assert str(row["at"]).endswith("+00:00")
    assert row["water"] == 1
